# -*- coding: utf-8 -*-

import json

from collections import defaultdict
from functools import partial
from tornado import web

from async import AsyncGroup
from handler import ReleaseHandler


JIRA_API_HOST = 'jira.hh.ru/rest/api/2/'
JIRA_API_ISSUE = JIRA_API_HOST + 'issue/{0}?fields=summary,customfield_11010,issuelinks'

GITHUB_API_HOST = 'https://api.github.com/'
GITHUB_API_BRANCHES_LIST = GITHUB_API_HOST + 'repos/hhru/{0}/branches'
GITHUB_API_BRANCH = GITHUB_API_HOST + '/repos/hh.ru/{0}/branches/{1}'
GITHUB_API_HHRU_BRANCH_DIFF = GITHUB_API_HOST + 'repos/hhru/hh.ru/compare/master...{0}'


REPOS = {'hh.sites.main'    : 'xhh',
         'hh.ru'            : 'hh.ru',
         'hh.sites.common'  : 'hh-common',}




class ReleaseInfoHandler(ReleaseHandler):
    def get_sql_from_branch(self, branch, async_group, context):
        def diff_cb(response):
            git_data = json.loads(response.body)
            for file_json in git_data.get('files', {}):
                raw_url = file_json.get('raw_url', '')
                if '.sql' in raw_url:
                    context['sqls']['hh.ru'].append(raw_url)
            
        self.make_github_request(url=GITHUB_API_HHRU_BRANCH_DIFF.format(branch), cb=async_group.add(diff_cb))
    
    def git_check_branches(self, release_branches, async_group, context):
        def branches_cb(context, repo, response):
            git_data = json.loads(response.body)
            repo_branches = map(lambda tree: tree.get('name', ''), git_data)
            for repo_branch in repo_branches:
                for release_branch in release_branches:
                    if release_branch in repo_branch:
                        if not context['issues'][release_branch].has_key('git_branches'):
                            context['issues'][release_branch]['git_branches'] = defaultdict(list)
                        context['issues'][release_branch]['git_branches'][REPOS.get(repo)].append(repo_branch)
                        
                        self.get_sql_from_branch(repo_branch, async_group, context)
                        
            
        for repo in REPOS:            
            url = GITHUB_API_BRANCHES_LIST.format(repo)
            self.make_github_request(url=url, cb=async_group.add(partial(branches_cb, context, repo)))
    

    @web.asynchronous
    def get(self):
        def release_cb(response):
            release_data = json.loads(response.body)
            release_includes = release_data.get('fields').get('issuelinks', [])
            issue_numbers = map(lambda issue: issue.get('outwardIssue').get('key'), release_includes)

            result_data = {'issues' : defaultdict(dict), 'sqls': {'hh.ru': []}}
            
            def group_cb():
                self.set_header('Content-Type', 'application/json')
                self.finish(json.dumps(result_data))
            
            def issue_cb(issue, response):
                issue_data = json.loads(response.body)
                result_data['issues'][issue].update({'summary': issue_data.get('fields').get('summary'), 
                                           'packages': issue_data.get('fields').get('customfield_11010')})
            
            if not issue_numbers:
                group_cb()
    
            async_group = AsyncGroup(group_cb)
            async_group.add_notification() #for local usage
            
            for issue in issue_numbers:
                url = JIRA_API_ISSUE.format(issue)
                self.make_jira_request(url=url, cb=async_group.add(partial(issue_cb, issue)))        

            self.git_check_branches(release_branches=issue_numbers, async_group=async_group, context=result_data)
            async_group.dec() # for loacal usage

        release = self.get_argument('release')
        url = JIRA_API_ISSUE.format(release)
        self.make_jira_request(url=url, cb=release_cb)

        