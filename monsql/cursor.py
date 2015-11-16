#!/usr/bin/env python
#coding:utf-8
# Author        : tuxpy
# Email         : q8886888@qq.com.com
# Last modified : 2015-11-16 09:58:20
# Filename      : cursor.py
# Description   : 
from __future__ import print_function, unicode_literals

def mysql_dict_cursor():
    from pymysql import cursors
    return cursors.DictCursor

def psql_dict_cursor():
    from psycopg2 import extras

    class _PsqlObjectDictCursor(extras.RealDictCursor):
        def __init__(self, *args, **kwargs):
            kwargs['row_factory'] = _PsqlObjectDictRow
            extras.DictCursorBase.__init__(self, *args, **kwargs)
            self._prefetch = 0

    class _PsqlObjectDictRow(extras.RealDictRow):
        def __getattr__(self, name):
            return self[name]

    return _PsqlObjectDictCursor

