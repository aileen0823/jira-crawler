import argparse
import json
from datetime import datetime
from http.cookiejar import MozillaCookieJar

import scrapy
from bs4 import BeautifulSoup
from scrapy.crawler import CrawlerProcess


class StoryStatusSpider(scrapy.Spider):
    name = 'storyStatusSpider'

    def __init__(self, cookies, jql, *args, **kwargs):
        super(StoryStatusSpider, self).__init__(*args, **kwargs)
        self.base_url = 'https://successware.atlassian.net/rest/issueNav/1/issueTable'
        # cookies_path = getattr(self, 'cookies', None)
        self.cookies = self.load_cookies(cookies)
        # self.cookies = self.load_cookies(cookies_path)
        print(self.cookies)
        print(jql)
        self.formdata = {"startIndex": "0",
                         "jql": jql,
                         "layoutKey": "list-view"}

    def load_cookies(self, cookies_dir):
        cj = MozillaCookieJar()
        cj.load(cookies_dir)

        cookies = {}
        for cookie in cj:
            cookies[cookie.name] = cookie.value
        return cookies

    def start_requests(self):
        return [scrapy.FormRequest(url=self.base_url,
                                   cookies=self.cookies,
                                   method='POST',
                                   headers={
                                       'x-atlassian-token': 'no-check'
                                   },
                                   formdata=self.formdata,
                                   callback=self.parse_issues)]

    def parse_issues(self, response):
        res_data = json.loads(response.text)
        issue_table = res_data.get('issueTable', {})
        start_index = issue_table.get('startIndex')
        page_size = issue_table.get('pageSize')
        total = issue_table.get('total', 0)
        current_page = int(start_index / page_size)
        total_page = int(total / page_size)

        print(f'begin parse page: {current_page}.....')
        # parse issue_key issue_type sprint
        table_str = issue_table.get('table', '').replace('\n', '')

        table = BeautifulSoup(table_str)
        thead = table.find('thead')
        headers = []
        for th in thead.find_all('th'):
            header_name = th.attrs.get('data-id', '')
            if 'customfield' in header_name:
                header_name = th.find('span').get_text()
            headers.append(header_name)

        tbody = table.find('tbody')
        for row in tbody.find_all('tr'):
            columns = row.find_all('td')
            col_dict = {}
            for i, col in enumerate(columns):
                col_name = headers[i] if headers[i] else col.attrs.get('class')[0]
                col_val = col.find('img').attrs.get('alt') if col_name == 'issuetype' else col.get_text()
                col_dict[col_name] = col_val.strip()
            issue_key = col_dict.get('issuekey')
            issue_url = f'https://successware.atlassian.net/rest/internal/2/issue/{issue_key}/activityfeed?startAt=0'
            print(f'start request history of issue: {issue_key}, \nurl: {issue_url}')
            yield scrapy.Request(url=issue_url,
                                 cookies=self.cookies,
                                 callback=self.parse_history,
                                 dont_filter=True,
                                 meta=col_dict)

        if current_page < total_page:
            next_start_index = start_index + page_size
            self.formdata.update({'startIndex': str(next_start_index)})
            yield scrapy.FormRequest(url=self.base_url,
                                     cookies=self.cookies,
                                     method='POST',
                                     headers={
                                         'x-atlassian-token': 'no-check'
                                     },
                                     formdata=self.formdata,
                                     callback=self.parse_issues)

    def parse_history(self, response):
        issue = response.meta
        issue['finalStatus'] = issue.pop('status')
        res_data = json.loads(response.text)
        items = res_data.get('items', [])
        status_items = list(filter(lambda item: item.get('fieldId', '') == 'status', items))

        for i, status_item in enumerate(status_items):
            author = status_item.get('actor', {}).get('displayName')
            timestamp = status_item.get('timestamp', 0) / 1000
            time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            start_status = status_item.get('from', {}).get('displayValue')
            end_status = status_item.get('to', {}).get('displayValue')

            if i == 0:
                first_status = {
                    'Owner': author,
                    'time': '',
                    'status': start_status
                }
                first_status.update(issue)
                yield first_status

            status_change = {
                'Owner': author,
                'time': time,
                'status': end_status
            }
            yield status_change


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jql", help="jql")
    parser.add_argument("--cookies", help="the absolute directory of cookies.txt")
    args = parser.parse_args()

    process = CrawlerProcess()
    process.crawl(StoryStatusSpider, cookies=args.cookies, jql=args.jql)
    process.start()


if __name__ == "__main__":
    main()
