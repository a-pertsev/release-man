# -*- coding: utf-8 -*-

from tornado import curl_httpclient


class HttpClient(object):
    @classmethod
    def instance(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = curl_httpclient.CurlAsyncHTTPClient(max_clients = 200, max_simultaneous_connections = 200)
        return cls._instance

