import argparse
import json
import time
from datetime import datetime
from http.cookiejar import MozillaCookieJar

import scrapy
from scrapy.crawler import CrawlerProcess


class BusinessBoardSpider(scrapy.Spider):
    name = 'businessBoardSpider'

    def __init__(self, cookies, *args, **kwargs):
        super(BusinessBoardSpider, self).__init__(*args, **kwargs)
        self.base_url = 'https://successware.atlassian.net/jsw/graphql'
        self.cookies = self.load_cookies(cookies)
        print(self.cookies)

    def load_cookies(self, cookies_dir):
        cj = MozillaCookieJar()
        cj.load(cookies_dir)

        cookies = {}
        for cookie in cj:
            cookies[cookie.name] = cookie.value
        return cookies

    def load_request(self):
        # f = open('/Users/siping.liu/workspace/study/crawler/jiraboard/jiraboard/spiders/request.json',)
        req = {
            "operationName": "SoftwareBoardScopeData",
            "query": "query SoftwareBoardScopeData ($boardId: ID!) {\n            boardScope(boardId: $boardId) {\n                userSwimlaneStrategy\n                board {\n                    etag\n                    name\n                    swimlaneStrategy\n                    hasClearedIssues\n                    rankCustomFieldId\n                    assignees { \n                        accountId\n                        displayName\n                        avatarUrl\n                    }\n                    columns {\n                        id\n                        name\n                        maxIssueCount\n                        status {\n                            id\n                            name\n                        }\n                        columnStatus {\n            status {\n                id\n                name\n                category\n            }\n            transitions {\n                id\n                name\n                status { \n                    id\n                }\n                originStatus { id }\n                cardType { id }\n                isGlobal\n                isInitial\n                hasConditions\n            }\n        }\n                        isDone\n                        isInitial\n                        transitionId\n                        cards {\n                            id\n                            flagged\n                            done\n                            parentId\n                            estimate { storyPoints }\n                            issue {\n                                id\n                                key\n                                summary\n                                labels\n                                assignee {\n                                    accountId\n                                    displayName\n                                    avatarUrl\n                                }\n                                type { id, name, iconUrl }\n                                status { id }\n                            }\n                            coverMedia {\n                                attachmentId\n                                endpointUrl\n                                clientId\n                                token\n                                attachmentMediaApiId\n                                hiddenByUser\n                            }\n                            priority {\n                                name\n                                iconUrl\n                            }\n                            dueDate\n                            childIssuesMetadata { complete, total }\n                        }\n                    }\n                    issueTypes {\n                        id\n                        name\n                        iconUrl\n                        hierarchyLevelType\n                    }\n                    inlineIssueCreate { enabled }\n                    cardMedia { enabled }\n                    issueChildren {\n                id\n                flagged\n                done\n                parentId\n                estimate { storyPoints }\n                issue {\n                    id\n                    key\n                    summary\n                    labels\n                    assignee {\n                        accountId\n                        displayName\n                        avatarUrl\n                    }\n                    type { id, name, iconUrl }\n                    status { id }\n                }\n                coverMedia {\n                    attachmentId\n                    endpointUrl\n                    clientId\n                    token\n                    attachmentMediaApiId\n                    hiddenByUser\n                }\n                priority {\n                    name\n                    iconUrl\n                }\n                dueDate\n            }\n                    \n                }\n                backlog {\n                    boardIssueListKey\n                    requestColumnMigration\n                }\n                sprints(state: [ACTIVE]) { \n                    id\n                    name\n                    goal\n                    startDate\n                    endDate\n                    daysRemaining\n                }\n                features { key, status, toggle, category }\n                projectLocation {\n                    id\n                    key\n                    name\n                    isSimplifiedProject\n                    issueTypes {\n                        id\n                        name\n                        iconUrl\n                        hierarchyLevelType\n                    }\n                }\n                issueParents {\n                    id\n                    key\n                    summary\n                    issue { status { id } }\n                    issueType {\n                        id\n                        name\n                        iconUrl\n                    }\n                    color\n                }\n                currentUser { permissions }\n            }\n        }",
            "variables": {
                "boardId": 21
            }
        }
        return json.dumps(req)

    def start_requests(self):
        return [scrapy.Request(url=self.base_url,
                               cookies=self.cookies,
                               method='POST',
                               headers={
                                   'content-type': 'application/json'
                               },
                               body=self.load_request(),
                               callback=self.parse_board)]

    def parse_board(self, response):
        res_data = json.loads(response.text)
        columns = res_data.get('data', {}).get('boardScope', {}).get('board', {}).get('columns', [])
        for column in columns:
            cards = column.get('cards', [])
            for card in cards:
                origin_issue = card.get('issue', {})
                issue_dict = {
                    'issuekey': origin_issue.get('key'),
                    'summary': origin_issue.get('summary'),
                    'assignee': origin_issue.get('assignee').get('displayName') if origin_issue.get('assignee') else '',
                    'type': origin_issue.get('type', {}).get('name')
                }
                issue_key = issue_dict.get('issuekey')
                issue_url = f'https://successware.atlassian.net/rest/api/3/issue/{issue_key}?fields=creator,created'
                print(f'start request created status of issue: {issue_key}, \nurl: {issue_url}')
                yield scrapy.Request(url=issue_url,
                                     cookies=self.cookies,
                                     callback=self.parse_created_status,
                                     dont_filter=True,
                                     meta=issue_dict)

    def parse_created_status(self, response):
        res_data = json.loads(response.text)
        issue_dict = response.meta
        issue_dict.update({
            'created_time': res_data.get('fields').get('created')
        })
        issue_key = issue_dict.get('issuekey')
        issue_url = f'https://successware.atlassian.net/rest/internal/2/issue/{issue_key}/activityfeed?startAt=0'
        print(f'start request history status of issue: {issue_key}, \nurl: {issue_url}')
        yield scrapy.Request(url=issue_url,
                             cookies=self.cookies,
                             callback=self.parse_history_status,
                             dont_filter=True,
                             meta=issue_dict)

    def parse_history_status(self, response):
        issue_dict = response.meta
        res_data = json.loads(response.text)
        items = res_data.get('items', [])
        status_items = list(filter(lambda item: item.get('fieldId', '') == 'status', items))
        create_timestamp = time.mktime(
            datetime.strptime(issue_dict.get('created_time'), "%Y-%m-%dT%H:%M:%S.%f%z").timetuple())
        create_time = datetime.fromtimestamp(create_timestamp).strftime('%Y-%m-%d %H:%M:%S')

        for i, status_item in enumerate(status_items):
            author = status_item.get('actor', {}).get('displayName')
            timestamp = status_item.get('timestamp', 0) / 1000
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            start_status = status_item.get('from', {}).get('displayValue')
            end_status = status_item.get('to', {}).get('displayValue')

            if i == 0:
                created_status = {
                    'Owner': author,
                    'time': create_time,
                    'status': 'created the issue'
                }
                created_status.update(issue_dict)
                yield created_status

                first_status = {
                    'Owner': author,
                    'time': '',
                    'status': start_status
                }
                yield first_status

            status_change = {
                'Owner': author,
                'time': time_str,
                'status': end_status
            }
            yield status_change


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookies", help="the absolute directory of cookies.txt")
    args = parser.parse_args()

    process = CrawlerProcess()
    process.crawl(BusinessBoardSpider, cookies=args.cookies)
    process.start()


if __name__ == "__main__":
    main()
