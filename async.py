# -*- coding: utf-8 -*-

class AsyncGroup(object):
    def __init__(self, finish_cb):
        self.count = 0
        self.finish_cb = finish_cb
        

    def dec(self):
        self.count = self.count - 1
        if self.count == 0:
            self.finish_cb()


    def add(self, cb):
        self.count = self.count + 1
        
        def group_cb(*args, **kwargs):
            cb(*args, **kwargs)
            self.dec()
        
        return group_cb

    def add_notification(self):
        return self.add(lambda *a, **kw: None)