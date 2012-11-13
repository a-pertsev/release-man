# -*- coding: utf-8 -*-

import pickle
import base64
import logging
import sys

from tornado import web, httpclient
from urllib import urlencode

from http_client import HttpClient

LOCAL_DUMP = False
LOCAL_DIR = 'local_info/'
LOCAL_WORK = True

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


try:
    from passwords import passwords
except ImportError:
    logging.error('Passwords must be declared in passwords.py module')
    sys.exit()


def get_auth_header(user, password):
    b64 = base64.b64encode('{0}:{1}'.format(user, password))
    return {'Authorization': 'Basic {0}'.format(b64)}    


class ResponseStub(object):
    def __init__(self, body):
        self.body = body


class ReleaseHandler(web.RequestHandler):
    def get_error_html(self, status_code, **kwargs):
        result = {'error': status_code}
        if kwargs.has_key('error_message'):
            result.update(message=kwargs['error_message'])
        return result

    def make_request(self, url, data='', headers={}, cb=lambda x: None):
        file_name = base64.b64encode(url)
        
        if LOCAL_WORK:
            logging.info('Local request: {0}'.format(url))
            with open(LOCAL_DIR + file_name, 'r') as f:
                cb(ResponseStub(pickle.loads(f.read())))
            return
                
        def dumped_cb(response):
            if LOCAL_DUMP:
                with open(LOCAL_DIR + file_name, 'w+') as f:
                    f.write(pickle.dumps(response.body))
            cb(response)
        
        body = urlencode(data) if isinstance(data, dict) else data
        if body:
            url = url + '?' + body
        
        req = httpclient.HTTPRequest(
                    url=url,
                    method='GET',
                    headers=headers,
                    connect_timeout=5,
                    request_timeout=10)
        
        logging.info('External request: {0}'.format(url))
        HttpClient.instance().fetch(req, dumped_cb)
        
        
    def make_jira_request(self, *args, **kwargs):
        return self.make_request(*args, headers=get_auth_header(*passwords.get('jira')), **kwargs)

    def make_github_request(self, *args, **kwargs):
        return self.make_request(*args, headers=get_auth_header(*passwords.get('github')), **kwargs)
    