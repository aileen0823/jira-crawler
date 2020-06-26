# jira-crawler
###
```scrapy list```

```scrapy crawl businessBoardSpider -o business.csv -t csv -a cookies=/Users/siping.liu/Downloads/cookies.txt```

```scrapy crawl storyStatusSpider -o story-status.csv -t csv -a cookies=/Users/siping.liu/Downloads/cookies.txt -a jql='issuetype in (Bug, Epic, SPIKE, Story) AND project = SP AND Sprint in (59, 57, 58, 67, 66, 70) ORDER BY cf[10020] DESC, status DESC, key ASC, summary ASC, lastViewed DESC'```
