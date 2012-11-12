# -*- coding: utf-8 -*-

import os
import sys
import logging
import signal

from daemon import pidlockfile, daemon
from datetime import datetime

from tornado import web, ioloop, httpserver

from release_info_handler import ReleaseInfoHandler

PIDFILE = 'release.pid'


logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


def init_application():
    
    routes = [
        (r"/()", web.StaticFileHandler, {"path": "main.html"}),
        (r'/ajax/get_release_info', ReleaseInfoHandler),
        (r"/static/(.*)", web.StaticFileHandler, {"path": "static/"}),
    ]
    
    app = web.Application(routes, debug=True)
    http_server = httpserver.HTTPServer(app)
    http_server.bind(9999)
    http_server.start()
    

    def stop_handler(signum, frame):
        logging.info('Requested shutdown')
        http_server.stop()

        if ioloop.IOLoop.instance().running():
            logging.info('Stoppinig ioloop')
            ioloop.IOLoop.instance().stop()
            logging.info('Server stoped')

        signal.signal(signal.SIGTERM, signal.SIG_IGN)

    signal.signal(signal.SIGTERM, stop_handler)

    logging.info('Server started')
    
    ioloop.IOLoop.instance().start()    
       
       
def start_server():
    logging.info('Server starting at: {0}'.format(datetime.now()))

    pid = None
    try:
        pid = pidlockfile.read_pid_from_pidfile(PIDFILE)
    except OSError:
        pass
    
    if pid is not None:
        try:
            os.getpgid(pid)
        except OSError:
            pidlockfile.remove_existing_pidfile(PIDFILE)
        else:
            init_application()
            return

    try:
        pidlockfile.write_pid_to_pidfile(PIDFILE)
    except OSError:
        logging.error('Pid file already exist, process must be running')
        sys.exit()
    
    init_application()

    
def stop_server():
    logging.info('Stopping server')

    pid = pidlockfile.read_pid_from_pidfile(PIDFILE)
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        logging.error('No such a process - cannot kill it')
    except TypeError:
        logging.error('Error reading pid file')
        
    pidlockfile.remove_existing_pidfile(PIDFILE)


def start_as_daemon():
    log = open('release.log', 'w+')
    ctx = daemon.DaemonContext(working_directory='.',
                               stderr=log,
                               stdout=log)
    ctx.open()
    start_server()    

       
       
if __name__ == '__main__':
    if len(sys.argv) == 1:
        start_server()
        
    else:
        if 'stop' in sys.argv:
            stop_server()
            sys.exit()    
            
        if 'restart' in sys.argv:
            try:
                stop_server()
            except:
                pass
            start_as_daemon()
        
        if 'start' in sys.argv:
            start_as_daemon()

