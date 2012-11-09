# -*- coding: utf-8 -*-

import json
import re
import logging


from copy import deepcopy
from collections import defaultdict
from functools import partial
from tornado import web

import utils
from async import AsyncGroup
from handler import ReleaseHandler

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


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
GITHUB_API_BRANCH_DIFF = GITHUB_API_HOST + 'repos/hhru/{repo}/compare/master...{branch}'

REPOS = {'hh.sites.main'    : 'xhh',
         'hh.ru'            : 'hh.ru',
         'hh.sites.common'  : 'hh-common',}

SQL_REPOS = ['hh.ru', 'hh.sites.main']


class ReleaseInfo(object):
    def __init__(self):
        self.errors = {}
        self.release = {'issues': defaultdict(dict), 'sqls': defaultdict(list)}
        self.release_variants = []

    def get_json(self):
        result = deepcopy(self.__dict__)
        return utils.clean(result)


class ReleaseInfoHandler(ReleaseHandler):
    def get_sql_from_branch(self, repo, branch, async_group):
        def diff_cb(response):
            git_data = json.loads(response.body)
            for file_json in git_data.get('files', {}):
                raw_url = file_json.get('raw_url', '')
                if '.sql' in raw_url:
                    self.result.release['sqls'][repo].append(raw_url)
            
        self.make_github_request(url=GITHUB_API_BRANCH_DIFF.format(repo=repo, branch=branch), cb=async_group.add(diff_cb))
    
    def git_check_branches(self, release_branches, async_group):
        def branches_cb(repo, response):
            git_data = json.loads(response.body)
            repo_branches = map(lambda tree: tree.get('name', ''), git_data)
            for repo_branch in repo_branches:
                for release_branch in release_branches:
                    if release_branch in repo_branch:
                        self.result.release['issues'][release_branch]['git_branches'][REPOS.get(repo)].append(repo_branch)
                        
                        if repo in SQL_REPOS:
                            self.get_sql_from_branch(repo, repo_branch, async_group)
                        

        for release_branch in release_branches:
            self.result.release['issues'][release_branch]['git_branches'] = defaultdict(list)

        for repo in REPOS:
            url = GITHUB_API_BRANCHES_LIST.format(repo)
            self.make_github_request(url=url, cb=async_group.add(partial(branches_cb, repo)))
    


    @web.asynchronous
    def get(self):
        self.result = ReleaseInfo()
        
        def release_cb(response):
            release_data = json.loads(response.body)
            if release_data.get('errorMessages') is not None:
                logging.error('issue getting error: {0}: {1}'.format(release_task, release_data.get('errorMessages')))
                self.finish({'errorMessage': '{0}: Issue does not exits'.format(release_task)}, result_code=404)
                return
            
            release_includes = release_data.get('fields').get('issuelinks', [])
            issue_numbers = map(lambda issue: issue.get('outwardIssue').get('key'), release_includes)

            def group_cb():
                self.finish()
            
            def issue_cb(issue, response):
                issue_data = json.loads(response.body)
                self.result.release['issues'][issue].update({'summary': issue_data.get('fields').get('summary'), 
                                           'packages': issue_data.get('fields').get('customfield_11010')})
            
            if not issue_numbers:
                group_cb()
    
            async_group = AsyncGroup(group_cb)
            async_group.add_notification() #for local usage
            
            for issue in issue_numbers:
                url = JIRA_API_ISSUE.format(issue)
                self.make_jira_request(url=url, cb=async_group.add(partial(issue_cb, issue)))        

            self.git_check_branches(release_branches=issue_numbers, async_group=async_group)
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
                    self.send_error(status_code=404, error_message='Cannot find release issue')
                    
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


    def finish(self, chunk=None, result_code=None):
        if chunk is not None:
            result = chunk
        else:
            result = self.result.get_json()
        if result_code is not None:
            self.set_status(result_code)
        super(ReleaseInfoHandler, self).finish(result)
        
        