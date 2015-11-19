#!/usr/bin/env python
#coding:utf-8
# Author        : tuxpy
# Email         : q8886888@qq.com.com
# Last modified : 2015-11-16 09:58:20
# Filename      : cursor.py
# Description   : 
from __future__ import print_function, unicode_literals
from .util import utf8

def mysql_dict_cursor():
    from pymysql import cursors
    class _MysqlObjectDictCursor(cursors.DictCursor):
        def mogrify(self, query, args = None):
            query = utf8(query)
            if not args:
                return query
            if isinstance(query , (tuple, list)):
                args = tuple([ utf8(arg) for arg in args])
            else:
                args = dict((utf8(key), utf8(value)) \
                        for key, value in args.items())
            conn = self._get_db()
            query = query % self._escape_args(args, conn)

            return query

    return _MysqlObjectDictCursor

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

