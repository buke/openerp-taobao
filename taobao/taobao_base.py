# -*- coding: utf-8 -*-
##############################################################################
#    Taobao OpenERP Connector
#    Copyright 2012 wangbuke <wangbuke@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#    For Commercial or OEM, you need to contact the author and/or licensor
#    and ask for their permission.
#
#    本程序基于AGPL协议发布。在遵守本协议的基础上，您可以本程序用于非商业用途。
#    商业使用及二次开发，您需要联系并得到作者的许可。以上内容如有未尽事宜或冲
#    突以英文内容为准。
##############################################################################

from osv import fields, osv
from osv import orm
import time, datetime
import openerp.tools as tools

from .taobao_top import TOPException
from psycopg2.extensions import TransactionRollbackError
from psycopg2 import DataError

import logging
_logger = logging.getLogger(__name__)
import openerp.tools.config as config

import sys,os
sys.path.append (os.path.abspath(os.path.join(os.path.dirname(__file__), 'libs')))
import beanstalkc
from decorator import decorator

import cPickle
beanstalk = None
NAME2FUNC = {}

def mq_client(func):
    name = func.__name__
    NAME2FUNC[name] = func
    def _func(func, *args, **kwds):
        global beanstalk
        if beanstalk is None:
            beanstalk = beanstalkc.Connection(host=config.get('beanstalkd_interface', 'localhost'), port= int(config.get('beanstalkd_port', 11300)))
            beanstalk.use('taobao_stream')

        s = cPickle.dumps((name, args, kwds))
        beanstalk.put(s)
    return decorator(_func, func)

def mq_server():
    beanstalk = beanstalkc.Connection(host=config.get('beanstalkd_interface', 'localhost'), port= int(config.get('beanstalkd_port', 11300)))
    beanstalk.watch('taobao_stream')
    beanstalk.ignore('default')

    while True:
        try:
            job = beanstalk.reserve()
        except:
            import traceback
            exc = traceback.format_exc()
            _logger.error(exc)
            time.sleep(1/1000)
            continue

        try:
            name, args, kwds = cPickle.loads(job.body)
            func = NAME2FUNC.get(name)
        except:
            import traceback
            exc = traceback.format_exc()
            _logger.error(exc)
            job.delete()
            continue

        try:
            func(*args, **kwds)
            job.delete()

        except TOPException:
            import traceback
            exc = traceback.format_exc()
            _logger.error(exc)
            job.delete()

        except osv.except_osv:
            import traceback
            exc = traceback.format_exc()
            _logger.error(exc)
            job.delete()

        except TransactionRollbackError: #TransactionRollbackError: 错误:  由于同步更新而无法串行访问
            job.release(delay = 1)

        except DataError: #DataError: 错误:  无效的 "UTF8" 编码字节顺序: 0xad
            import traceback
            exc = traceback.format_exc()
            _logger.error(exc)
            job.delete()

        except:
            import traceback
            exc = traceback.format_exc()
            _logger.error(exc)
            job.release(delay = 1)

        finally:
            time.sleep(1/1000)


STREAM_MSG_ROUTER = {}
def msg_route(**kwargs):
    def decorator(callback):
        STREAM_MSG_ROUTER[tuple(sorted(kwargs.items(), key=lambda x:x[0]))] = callback
        return callback
    return decorator

import threading
from functools import wraps
_lock=threading.RLock()

def lock():
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                _lock.acquire()
                return func(self, *args, **kwargs)
            finally:
                _lock.release()
        return wrapper
    return decorator

class TaobaoException(Exception):
    def __init__(self, msg):
        super(TaobaoException, self).__init__(msg)

class TaobaoMixin:

    def _get(self, cr, uid, ids = None, args = []):
        if not ids:
            ids = self.search(cr, uid, args)

        if not ids: return None

        ret = self.browse(cr, uid, ids)
        if isinstance(ret, orm.browse_record_list):
            return ret[0]
        else:
            return ret

    def _save(self, cr, uid, ids = None, args = None, **kwargs):
        vals = {}
        for k, v in [(str(k), v) for (k, v) in kwargs.iteritems()]:
            if self._columns.has_key(k) and v != None:
                if isinstance(self._columns[k], fields.boolean):
                    vals[k] = bool(v)
                    continue
                if isinstance(self._columns[k], fields.integer):
                    vals[k] = int(v)
                    continue
                if isinstance(self._columns[k], fields.char):
                    if type(v) == unicode:
                        vals[k] = unicode(v).strip()
                    else:
                        vals[k] = str(v).strip()
                    continue
                if isinstance(self._columns[k], fields.text):
                    vals[k] = type(v)(v).strip()
                    continue
                if isinstance(self._columns[k], fields.float):
                    vals[k] = float(v)
                    continue
                if isinstance(self._columns[k], fields.date):
                    if type(v) == str or type(v) == unicode:
                        vals[k] = type(v)(v).strip()
                    elif type(v) == datetime.datetime or type(v) == time:
                        vals[k] = type(v).strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
                    continue
                if isinstance(self._columns[k], fields.datetime):
                    if type(v) == str or type(v) == unicode:
                        vals[k] = type(v)(v).strip()
                    elif type(v) == datetime.datetime or type(v) == time:
                        vals[k] = type(v).strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)
                    continue
                if isinstance(self._columns[k], fields.time):
                    if type(v) == str or type(v) == unicode:
                        vals[k] = type(v)(v).strip()
                    elif type(v) == datetime.datetime or type(v) == time:
                        vals[k] =type(v).strftime(tools.DEFAULT_SERVER_TIME_FORMAT)
                    continue

                vals[k] = v

        if (not ids) and args:
            ids = self.search(cr, uid, args)

        if ids:
            self.write(cr, uid, ids, vals)
        else:
            ids = self.create(cr, uid, vals)

        ret = self.browse(cr, uid, ids)
        if isinstance(ret, orm.browse_record_list):
            return ret[0]
        else:
            return ret


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
#    商业使用及二次开发，您需要联系并得到作者的许可。
