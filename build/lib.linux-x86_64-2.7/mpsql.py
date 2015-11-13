#!/usr/bin/env python
#coding:utf-8
# Author        : tuxpy
# Email         : q8886888@qq.com.com
# Last modified : 2015-07-08 12:54:28
# Filename      : psql.py
# Description   : 
from __future__ import print_function, unicode_literals
import psycopg2
from psycopg2 import extras
import logging
from tornado.escape import utf8
from functools import partial

sql_log = logging.getLogger('psql')

class ObjectDictCursor(extras.RealDictCursor):
    def __init__(self, *args, **kwargs):
        kwargs['row_factory'] = ObjectDictRow
        extras.DictCursorBase.__init__(self, *args, **kwargs)
        self._prefetch = 0

class ObjectDictRow(extras.RealDictRow):
    def __getattr__(self, name):
        return self[name]

def generate_json_where(field, key, value, rel = None, _type = None):
    """会返回字典格式"""
    if _type == None:
        _type = (isinstance(value, int) or value.isdigit()) and 'int' or 'text'

    _key = "(%s->>'%s')::%s" % (field, key, _type)

    if rel == None or rel == "$eq":
        _value = value
    else:
        assert rel[0] == '$'
        _value = {rel: value}

    return {_key: _value}

def config_logging():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(filename)s:%(lineno)s %(message)s')
    handler.setFormatter(formatter)
    sql_log.addHandler(handler)
    sql_log.setLevel(logging.DEBUG)

class Record(object):
    def __init__(self, _cur):
        self._cur = _cur

    def __iter__(self):
        while True:
            record = self.next()
            if not record:
                break
            else:
                yield record

    def next(self):
        return self._cur.fetchone()

    def __len__(self):
        return self._cur.rowcount

class PsqlTable(object):
    def __init__(self, table_name, conn = None, cur = None, debug = False): # conn是指psql的connect产生的对象
        if isinstance(table_name, unicode):
            table_name = table_name.encode('utf-8')
        self.table_name = table_name
        self._cur = cur or conn.cursor()
        self.conn = conn
        self.debug = debug

    def __inner_join(self, join):
        if not join:
            return ''
        assert isinstance(join, (dict, list, tuple))
        if isinstance(join, dict):
            join_items = join.items()
        else:
            join_items = join

        join_str_list = []
        table_alias_counter = 1

        for _item in join_items:
            _column_1, _column_2, _join_type = (list(_item) + ['INNER'])[:3]
            assert '.' in _column_1 or '.' in _column_2
            is_join_column = '.' in _column_1 and _column_1 or _column_2
            if '.' in _column_1:
                join_column = _column_1
                old_column = _column_2
            else:
                join_column = _column_2
                old_column = _column_1

            if '.' not in old_column:
                old_column = self.table_name + '.' + old_column

            join_table = join_column.split('.')[0]

            _join_str = "{join_type} JOIN {table} as {table_alias} ON {old_column} = {table_alias}.{join_column}".format(
                    table = join_table, join_type = _join_type, 
                    table_alias = "t%s" % table_alias_counter, 
                    old_column = old_column, join_column = join_column.split('.', 1)[1])
            join_str_list.append(_join_str)
            table_alias_counter += 1

        return ' '.join(join_str_list) + ' '
            
    def find(self, cond = None, column = None, join_str = "", join = None, **ext_kwargs):
        assert not (join_str and join)
        cond = cond or {}
        column = column or []
        assert isinstance(cond, dict) and isinstance(column, (list, tuple))
        column_string = self.__cat_column_string(column)
        cond_string = self.__cat_cond_string(cond)
        ext_string = self.__cat_ext_string(**ext_kwargs)
        sql_string = "SELECT {column} FROM {table_name} ".format(
                column = column_string, table_name = self.table_name)
        sql_string += self.__inner_join(join) or (join_str + ' ')
        if isinstance(sql_string, unicode):
            sql_string = sql_string.encode('utf-8')
        if cond:
            sql_string += 'WHERE %s ' %(cond_string )
        sql_string += ext_string

        self.execute_sql(sql_string)
        if self._cur.rowcount == 0:
            return []
        return Record(self._cur)

    def find_one(self, *args, **kwargs):
        record_iter = self.find(*args, **kwargs)
        record = record_iter and record_iter.next() or {}
        del record_iter
        return record

    def update(self, set_value, cond = None, returning = None):
        """这里比较low，只允许简单的update set， 跟mongodb不同的是，条件在后面[]"""
        cond = cond or {}
        assert isinstance(cond, dict) and isinstance(set_value, dict)
        set_string = self.__cat_set_string(set_value)
        cond_string = self.__cat_cond_string(cond)
        sql_string = 'UPDATE ' + self.table_name + ' set ' + set_string
        if cond:
            sql_string += ' WHERE ' + cond_string

        return self.execute_sql(sql_string, returning)

    def remove(self, cond = None, returning = None):
        cond = cond  or {}
        sql_string = 'DELETE FROM ' + self.table_name
        cond_string = self.__cat_cond_string(cond)
        if cond:
            sql_string += ' WHERE ' + cond_string

        return self.execute_sql(sql_string, returning)

    def insert(self, record_list, returning = None):
        """returning 可以接受一个列表，表示insert后要返回的字段，空列表表示返回所有字段"""
        result = []
        if isinstance(record_list, dict):
            record_list = [record_list]
        for record in record_list:
            sql_string = 'INSERT INTO ' + self.table_name + ' ('
            sql_string += ', '.join(record.keys()) + ') VALUES('
            sql_string += ', '.join(["%({0})s".format(k) for k in record.keys()]) + ') '
            sql_string = self._cur.mogrify(sql_string, record)
            result.append(self.execute_sql(sql_string, returning))


        if len(result) == 1:
            return result[0]
        return result

    def __generate_set_string(self, left_value, right_value):
        """解析update set时带函数问题"""
        _k, _v = left_value, right_value
        if not isinstance(right_value, dict):
            return self._cur.mogrify('{name}=%({name})s'.format(name = 
                left_value), {left_value: right_value})

        left_value, right_value = right_value.items()[0]
        assert left_value[0] == '&' # 表示是个函数
        func_name = left_value[1:]
        func_args = right_value

        return self._cur.mogrify('{name}={func_name}({func_args})'.format(
            name = _k, func_name = func_name, 
            func_args = ', '.join(map(unicode, func_args))))

        return '{name}=%({name})s'.format

    def __cat_set_string(self, set_value):
        _set_list = []
        for _k, _v in set_value.items():
            _set_list.append(self.__generate_set_string(_k, _v).decode('utf-8'))

        return ', '.join(_set_list)

    def __cat_ext_string(self, **ext):
        if not ext:
            return ''
        _ext_list = []
        for _k, _v in ext.items():
            if _v == None:
                continue
            _k = _k.replace('_', ' ').upper()
            _ext_list.append("%s %s" %(_k, _v))

        return ' '.join(_ext_list)

    def __call__(self, *args, **kwargs):
        return self.execute_sql(*args, **kwargs)

    @property
    def rel_table_name(self):
        rel = self.table_name
        if '.' in rel:
            rel = rel.split('.')[-1]

        return rel

    @property
    def nsp_table_name(self):
        if '.' not in self.table_name:
            return 'public'

        return self.table_name.split('.')[0]

    def columns(self):
        pg_class = PsqlTable(debug = False, cur = self._cur, table_name = 'pg_class')
        oid = pg_class.find_one({'relname': self.rel_table_name,
            't1.nspname': self.nsp_table_name}, 
            ['pg_class.oid'], 
            join = [('relnamespace', 'pg_namespace.oid', 'LEFT')])['oid']

        sql = """SELECT a.attname as name,
          pg_catalog.format_type(a.atttypid, a.atttypmod) as type,a.attnotnull as not_null  
          FROM pg_catalog.pg_attribute a
          WHERE a.attrelid = '{oid}' AND a.attnum > 0 AND NOT a.attisdropped
          ORDER BY a.attnum;""".format(oid = oid)

        self.execute_sql(sql, debug = False)
        return list(Record(self._cur))

    def execute_sql(self, sql, returning = None, debug = None):
        sql = utf8(sql)
        debug = self.debug if debug == None else debug
        if isinstance(returning, list):
            sql += utf8(' RETURNING ' + (returning and ', '.join(returning) or '*'))

        if sql[-1] != utf8(';'):
            sql += utf8(';')

        self._cur.execute(utf8(sql))

        if debug:
            sql_log.info(utf8(sql))

        if returning == None:
            return

        return_data = self._cur.fetchall()
        if not return_data:
            return {}

        if len(return_data) == 1:
            return return_data[0]

        return return_data

    def __cat_column_string(self, column):
        if column == []:
            return '*'
        return ', '.join(column)

    def __cat_cond_string(self, cond):
        _cond = ''
        for _k, _v in cond.items():
            if _k[0] == '$':
                _conn_opera = _k[1:].upper()
                _sub_cond_string = ''
                for _sub_cond in _v:
                    _sub_cond_string += (_sub_cond_string and " %s " % _conn_opera or '') + self.__cat_cond_string(_sub_cond)
                _cond += '(' + _sub_cond_string + ')'

            else:
                _cond += (_cond and ' AND ' or '') + self.__made_real(_k, _v)

        return _cond

    def __made_real(self, key, value, opera = 'eq'): # 产生关系表达式，像xx = yy或xx > yy这样的
        _real = ''
        all_real_opera = {'eq': '=', 'in': 'IN', 'not': 'NOT', 'gt': '>', 'gte': '>=', 'ne': '!=', 
                'lt': '<', 'lte': '<='}
        opera = value != None and all_real_opera.get(opera.lower(), opera.lower()) or 'is'
        if isinstance(value, dict):
            for _k, _v in value.items():
                assert _k[0] == '$'
                _real_opera = _k[1:]
                _real += (_real and ' AND ' or '') + self.__made_real(key, _v, _real_opera)
        else:
            if isinstance(value, list) and \
                    opera not in  ('?&', '&&'): # 因为在做json或array操作时需要使用数组, 这时候就不可以转成tuple了
                value = tuple(value)
            _real = (_real and ' AND ' or '') + self._cur.mogrify("{name} {real_opera} %(real_key)s".format(
                name = key, real_opera = opera), {'real_key': value}).decode('utf-8')

        return _real

class Cursor(object): 
    def __init__(self, cur, debug, conn): 
        self._cur = cur
        self.debug = debug
        self._conn = conn

    def __getattr__(self, name):
        if name in dir(self._cur):
            return getattr(self._cur, name)
        else:
            return PsqlTable(name, cur = self._cur, debug = self.debug)

    def __getitem__(self, name):
        return self.__getattr__(name)

    def get_tables(self):
        records = self.pg_tables.find({'schemaname': 'public'})
            # sql list all tables: 
        return [record.tablename for record in records]

    def new(self, arg, kwargs):
        return Cursor(self._conn.cursor(*arg, **kwargs), self.debug, self._conn)

class PsqlConnection(object):
    _conn = None
    def __init__(self, *args, **kwargs):
        self.args = args
        kwargs.setdefault('cursor_factory', ObjectDictCursor)
        self.kwargs = kwargs
        self.debug = kwargs.pop('debug', False)
        if self.debug:
            config_logging()
    
    @property
    def __conn(self):
        if self._conn == None or self._conn.closed:
            self._conn = self.made_connect()

        return self._conn

    def made_connect(self):
        conn = psycopg2.connect(*self.args, **self.kwargs)
        print('psql connect')
        return conn

    def __getattr__(self, name): 
        if name in dir(self.__conn):
            return getattr(self.__conn, name)
        else:
            return PsqlTable(name, conn = self.__conn, debug = self.debug)

    def __getitem__(self, name):
        return self.__getattr__(name)

    def cursor(self, *args, **kwargs):
        _cur = Cursor(self.__conn.cursor(*args, **kwargs),
                self.debug, self.__conn)

        _cur.new = partial(_cur.new, args, kwargs)
        return _cur

