# -*- coding: utf-8 -*-

import pickle
import base64

from tornado import web, httpclient, curl_httpclient



http_client = curl_httpclient.CurlAsyncHTTPClient(max_clients = 200, max_simultaneous_connections = 200)
LOCAL_DIR = 'local_info/'
LOCAL_WORK = True

class ResponseStub(object):
    def __init__(self, body):
        self.body = body

class ReleaseHandler(web.RequestHandler):
    def make_request(self, url, data='', headers={}, cb=lambda x: None):
        
        file_name = base64.b64encode(url)
        
        if LOCAL_WORK:
            with open(LOCAL_DIR + file_name, 'r') as f:
                cb(ResponseStub(pickle.loads(f.read())))
            return
                
        def new_cb(response):
            with open(LOCAL_DIR + file_name, 'w+') as f:
                f.write(pickle.dumps(response.body))
            cb(response)
        
        
        req = httpclient.HTTPRequest(
                    url=url,
                    body=data,
                    method='GET',
                    headers=headers,
                    connect_timeout=5,
                    request_timeout=10)
        http_client.fetch(req, new_cb)