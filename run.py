# -*- coding: utf-8 -*-

import logging

from tornado import web, ioloop

from release_info_handler import ReleaseInfoHandler


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
       

if __name__ == '__main__':
    routes = [
        (r"/()", web.StaticFileHandler, {"path": "main.html"}),
        (r'/ajax/get_release_info', ReleaseInfoHandler),
        (r"/static/(.*)", web.StaticFileHandler,  {"path": "static/"}),
    ]
    app = web.Application(routes, debug=True)
    app.listen(9999)
    ioloop.IOLoop.instance().start()