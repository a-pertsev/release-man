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
    

def clean_filter(item):
    return item not in [[], {}, None]

def clean(data):
    if isinstance(data, (list,tuple)):
        for index, item in enumerate(data):
            data[index] = clean(item)
        return filter(clean_filter, data)
    
    if isinstance(data, dict):
        marked = []
        for key, value in data.iteritems():
            data[key] = clean(value)
            if not clean_filter(data[key]):
                marked.append(key)
        for key in marked:
            del(data[key])
        
    return data
