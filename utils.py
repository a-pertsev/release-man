# -*- coding: utf-8 -*-

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
            if clean_filter(data[key]):
                marked.append(key)
        for key in marked:
            del(data[key])
        
    return data
