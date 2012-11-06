# -*- coding: utf-8 -*-

from datetime import datetime
import sys
import logging
import daemon
import lockfile

from tornado import web, ioloop

from release_info_handler import ReleaseInfoHandler


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

       
if __name__ == '__main__':
    if len(sys.argv) > 1:
        if 'start' in sys.argv:
            log = open('release.log', 'w+')
            ctx = daemon.DaemonContext(pidfile=lockfile.FileLock('release.pid'),
                                       stderr=log,
                                       stdout=log)
            ctx.open()
       
    logging.info('Server starting at: {0}'.format(datetime.now()))
    
    routes = [
        (r"/()", web.StaticFileHandler, {"path": "main.html"}),
        (r'/ajax/get_release_info', ReleaseInfoHandler),
        (r"/static/(.*)", web.StaticFileHandler,  {"path": "static/"}),
    ]
    
    app = web.Application(routes, debug=True)
    app.listen(9999)
    
    ioloop.IOLoop.instance().start()

    logging.info('Server started')

