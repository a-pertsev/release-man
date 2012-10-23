# -*- coding: utf-8 -*-

import logging
import json
import base64

from collections import defaultdict
from functools import partial
from tornado import web, ioloop

from async import AsyncGroup
from handler import ReleaseHandler


JIRA_API_HOST = 'jira.hh.ru/rest/api/2/'
JIRA_API_ISSUE = JIRA_API_HOST + 'issue/{0}?fields=summary,customfield_11010,issuelinks'

GITHUB_API_HOST = 'https://api.github.com/'
GITHUB_API_BRANCH_CHECK = GITHUB_API_HOST + 'repos/hhru/{0}/branches'

REPOS = {'hh.sites.main'    : 'xhh',
         'hh.ru'            : 'hh.ru',
         'hh.sites.common'  : 'hh-common',}


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


def get_auth_header(user, password):
    b64 = base64.b64encode('{0}:{1}'.format(user, password))
    return {'Authorization': 'Basic {0}'.format(b64)}    

def get_jira_auth_header():
    return get_auth_header('jira_login', 'jira_password')


def get_github_auth_header():
    return get_auth_header('jira_login', 'github_password')



class ReleaseInfoHandler(ReleaseHandler):
    def git_check_branches(self, release_branches, async_group, context):
        def branches_cb(context, response):
            git_data = json.loads(response.body)
            repo_branches = map(lambda tree: tree.get('name', ''), git_data)
#            if filter(lambda repo_branch: issuerepo_branches)
            
        for repo in REPOS:            
            url = GITHUB_API_BRANCH_CHECK.format(repo)
            self.make_request(url=url, headers=get_github_auth_header(), cb=async_group.add(partial(branches_cb, context)))
    

    @web.asynchronous
    def get(self):
        def release_cb(response):
            release_data = json.loads(response.body)
            release_includes = release_data.get('fields').get('issuelinks', [])
            issue_numbers = map(lambda issue: issue.get('outwardIssue').get('key'), release_includes)

            result_data = defaultdict(dict)
            
            def group_cb():
                self.set_header('Content-Type', 'application/json')
                self.finish(json.dumps(result_data))
            
            def issue_cb(issue, response):
                issue_data = json.loads(response.body)
                result_data[issue].update({'summary': issue_data.get('fields').get('summary'), 
                                           'packages': issue_data.get('fields').get('customfield_11010')})
            
            if not issue_numbers:
                group_cb()
    
            async_group = AsyncGroup(group_cb)
    
            for issue in issue_numbers:
                url = JIRA_API_ISSUE.format(issue)
                self.make_request(url=url, headers=get_jira_auth_header(), cb=async_group.add(partial(issue_cb, issue)))        

            self.git_check_branches(release_branches=issue_numbers, async_group=async_group, context=result_data)


        release = self.get_argument('release')
        url = JIRA_API_ISSUE.format(release)
        self.make_request(url, '', get_jira_auth_header(), release_cb)
         
#        with open('jira_issue.pick', 'r') as f:
#            release_plain_data = json.loads(pickle.load(f))
#            
#        release_includes = release_plain_data.get('fields').get('issuelinks', [])
#        issue_numbers = map(lambda issue: issue.get('outwardIssue').get('key'), release_includes)



if __name__ == '__main__':
    routes = [
        (r"/()", web.StaticFileHandler, {"path": "main.html"}),
        (r'/ajax/get_release_info', ReleaseInfoHandler),
        (r"/static/(.*)", web.StaticFileHandler,  {"path": "static/"}),
    ]
    app = web.Application(routes, debug=True)
    app.listen(9999)
    ioloop.IOLoop.instance().start()