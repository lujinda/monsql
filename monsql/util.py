#!/usr/bin/env python
#coding:utf-8
# Author        : tuxpy
# Email         : q8886888@qq.com.com
# Last modified : 2015-11-15 22:46:13
# Filename      : util.py
# Description   : 

def utf8(s):
    if isinstance(s, unicode):
        return s.encode('utf-8')
    else:
        return s


