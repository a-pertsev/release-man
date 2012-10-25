# -*- coding: utf-8 -*-

import json
import re

from collections import defaultdict
from functools import partial
from tornado import web

from async import AsyncGroup
from handler import ReleaseHandler

RELEASE_VERSION_RE = re.compile('((?:[0-9]+.)+[0-9]+)')
RELEASE_ISSUE_PREFIX = 'EXP-'

JIRA_API_HOST = 'jira.hh.ru/rest/api/2/'
JIRA_API_ISSUE = JIRA_API_HOST + 'issue/{0}?fields=summary,customfield_11010,issuelinks'
JIRA_API_SEARCH = JIRA_API_HOST + 'search'
JIRA_RELEASE_SEARCH_DATA =  {'fields' : 'summary' ,
                             'jql' : 'project = EXP AND issuetype = "New Release" and created >= "-8d" ORDER BY created'}


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
                        context['issues'][release_branch]['git_branches'][REPOS.get(repo)].append(repo_branch)
                        
                        if repo == 'hh.ru':
                            self.get_sql_from_branch(repo_branch, async_group, context)
                        

        for release_branch in release_branches:
            context['issues'][release_branch]['git_branches'] = defaultdict(list)

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
                self.finish(result_data)
            
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
            async_group.dec() # for local usage


        def find_release_task(release_version):
            def search_cb(response):
                jira_data = json.loads(response.body)
                suitable_issues = []
                for issue in jira_data.get('issues', []):
                    if issue.get('fields', {}).get('summary') == release_version:
                        self.make_jira_request(url=JIRA_API_ISSUE.format(issue.get('key')), cb=release_cb)
                        return
                    if re.match('.*{0}([a-zA-Z-_ ]|$)'.format(release_version), issue.get('fields', {}).get('summary')):
                        suitable_issues.append(issue)
                
                if suitable_issues:
                    self.finish({'release_variants': suitable_issues})
                else:
                    self.send_error('404', error_message='Cannot find release issue')
                    
            self.make_jira_request(url=JIRA_API_SEARCH, data=JIRA_RELEASE_SEARCH_DATA, cb=search_cb)


        self.set_header('Content-Type', 'application/json')

        release_task = self.get_argument('release')
        
        if not release_task.startswith(RELEASE_ISSUE_PREFIX):
            if release_task.isdigit():
                release_task = RELEASE_ISSUE_PREFIX + release_task
            else:
                release_version = re.findall(RELEASE_VERSION_RE, release_task)
                if release_version:
                    find_release_task(release_version[0])
                    return
                else:
                    self.send_error(status_code=400, error_message='Bad release issue name')

        self.make_jira_request(url=JIRA_API_ISSUE.format(release_task), cb=release_cb)

        