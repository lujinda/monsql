#!/usr/bin/env python
#coding:utf-8
# Author        : tuxpy
# Email         : q8886888@qq.com.com
# Last modified : 2015-11-05 10:50:34
# Filename      : setup.py
# Description   : 
from distutils.core import setup
import monsql

setup(
        name = 'pymonsql',
        version = str(monsql.version),
        author = 'moment-x',
        packages = [
            'monsql',
            ],
        )

