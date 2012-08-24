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

from osv import osv, fields
import openerp.tools.config as config
from .taobao_top import TOP, _O
import json
import datetime
import time
from taobao_base import mq_client
from taobao_base import msg_route
from taobao_base import STREAM_MSG_ROUTER

import openerp
import logging
_logger = logging.getLogger(__name__)
from taobao_base import TaobaoMixin
import threading

CHECK_DISCARD_THREAD_START = {}

class taobao_shop(osv.osv, TaobaoMixin):
    _name = "taobao.shop"
    _description = "Taobao Shop"

    def _get_taobao_shop_url(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for shop in self.browse(cr, uid, ids, context=context):
            res[shop.id] = 'http://shop%s.taobao.com' % shop.taobao_shop_sid
        return res

    _columns = {
            'name': fields.char(u'店铺名字', size=256),
            'sale_shop_id': fields.many2one('sale.shop', 'Sale Shop', required=True, select=True),
            'taobao_shop_sid': fields.char(u'店铺编号', size=64),
            'taobao_shop_url': fields.function(_get_taobao_shop_url, type='char', string=u'店铺地址'),
            'taobao_nick': fields.char(u'卖家昵称', size=64 ),
            'taobao_user_id': fields.char(u'卖家数字ID', size=64 ),
            'taobao_app_key': fields.char('App Key', size=256, unique = True),
            'taobao_app_secret': fields.char('App Secret', size=256),
            'taobao_session_key': fields.char('Session Key', size=256),

            #taobao shop
            'enable_taobao_stream': fields.boolean(u'接收淘宝主动通知消息'),

            }


    _sql_constraints = [('taobao_app_key_uniq','unique(taobao_app_key)', 'Taobao Shop App Key must be unique!')]

    _defaults = {
            'enable_taobao_stream': True,
            }


    def create(self, cr, user, vals, context=None):
        try:
            top = TOP(vals['taobao_app_key'], vals['taobao_app_secret'], vals['taobao_session_key'])
            top('taobao.increment.customer.permit')
            tb_user = top('taobao.user.get', fields = ['user_id','nick']).user
            tb_shop = top('taobao.shop.get', nick = tb_user.nick, fields = ['sid','nick']).shop
            vals['taobao_shop_sid'] = tb_shop.sid
            vals['taobao_user_id'] = tb_user.user_id
            vals['taobao_nick'] = tb_user.nick
            if not vals.get('name', False):
                vals['name'] = tb_user.nick
            return super(taobao_shop, self).create(cr, user, vals, context=context)
        except:
            raise

    def write(self, cr, user, ids, vals, context=None):
        try:
            shop = self._get(cr, user, ids = ids)
            if not 'taobao_app_key' in vals.keys():
                vals['taobao_app_key'] = shop.taobao_app_key

            if not 'taobao_app_secret' in vals.keys():
                vals['taobao_app_secret'] = shop.taobao_app_secret

            if not 'taobao_session_key' in vals.keys():
                vals['taobao_session_key'] = shop.taobao_session_key

            top = TOP(vals['taobao_app_key'], vals['taobao_app_secret'], vals['taobao_session_key'])
            top('taobao.increment.customer.permit')
            tb_user = top('taobao.user.get', fields = ['user_id','nick']).user
            tb_shop = top('taobao.shop.get', nick = tb_user.nick, fields = ['sid','nick']).shop
            vals['taobao_shop_sid'] = tb_shop.sid
            vals['taobao_user_id'] = tb_user.user_id
            vals['taobao_nick'] = tb_user.nick

            return super(taobao_shop, self).write(cr, user, ids, vals, context)
        except:
            raise

    def __init__(self, pool, cr):
        super(taobao_shop, self).__init__(pool, cr)
        #pycurl两个函数不是线程安全。所以在主线程中进行一次的初始化和清除
        import pycurl
        pycurl.global_init(pycurl.GLOBAL_DEFAULT)
        pycurl.global_cleanup()


    def _start_worker_thread(self, cr, uid):
        """
        启动 taobao worker 线程
        """
        for i in range(int(config.get('taobao_worker_thread_limit', 4))):
            thread_name = 'taobao_worker_%s' % str(i)
            thread_exits = False
            for thread in threading.enumerate():
                if thread.getName() == thread_name:
                    thread_exits = True
                    break;

            if not thread_exits:
                from taobao_base import mq_server
                t = threading.Thread(target=mq_server, args = [], name=thread_name)
                t.setDaemon(True)
                t.start()

            time.sleep(50/1000)

    def _create_stream_thread(self, cr, uid, thread_name, shop):
        """
        创建链接 taobao stream 线程
        """
        #创建stream线程
        stream_thread_exits = False
        for thread in threading.enumerate():
            if thread.getName() == thread_name:
                stream_thread_exits = True
                break;

        if not stream_thread_exits:
            # check last discard_info
            global CHECK_DISCARD_THREAD_START
            if not CHECK_DISCARD_THREAD_START.get(shop.taobao_app_key, False):
                threading.Thread(target=self._check_discard_info, args=[cr.dbname, uid, shop.taobao_app_key]).start()
                CHECK_DISCARD_THREAD_START[shop.taobao_app_key] = True

            #start taobao stream
            stream_id = ''.join([config['xmlrpc_interface'] or '0.0.0.0', ':', str(config['xmlrpc_port']), '/', thread_name])

            t = threading.Thread(target=TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key).stream, args=[cr.dbname, uid, stream_id, shop.taobao_user_id, shop.taobao_nick], name=thread_name)
            t.setDaemon(True)
            t.start()


    def _start_stream_thread(self, cr, uid, shops):
        if not config.get('taobao_stream_service', True):
            return

        for shop in shops:
            if shop.taobao_app_key  and shop.enable_taobao_stream:
                for i in range(int(config.get('taobao_stream_thread_limit', 1))):
                    shop_thread_name = 'taobao_app_' + shop.taobao_app_key + str(i)
                    self._create_stream_thread(cr, uid, shop_thread_name, shop)


    def _check_discard_info(self, dbname, uid, app_key):
        try:
            pool = openerp.pooler.get_pool(dbname)
            cr = pool.db.cursor()
            tb_packet_obj = pool.get('taobao.packet')
            packet_ids = tb_packet_obj.search(cr, uid, [('taobao_app_key','=', app_key)], limit =1)
            if packet_ids:
                begin_str = tb_packet_obj.perm_read(cr, uid, packet_ids)[0].get('create_date').split('.')[0]
                begin = datetime.datetime.strptime(begin_str, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(hours = 8) - datetime.timedelta(minutes = 1)
                end = datetime.datetime.utcnow() + datetime.timedelta(hours = 8)

                job = {"taobao_app_key": app_key, "packet": {"msg": {"begin": int(time.mktime(begin.timetuple())*1000), "end": int(time.mktime(end.timetuple())*1000)}, "code": 203}}
                TaobaoMsgRouter(dbname, uid, app_key, job)
        except:
            import traceback
            exc = traceback.format_exc()
            _logger.error(exc)
        finally:
            cr.close()


    def stream(self, cr, uid, ids=False, context=None):
        if not ids: ids = self.search(cr, uid, [])
        if context is None: context = {}

        shops = self.browse(cr, uid, ids, context=context)
        if shops:
            self._start_worker_thread(cr, uid) # 启动worker 进程
            self._start_stream_thread(cr, uid, shops)

@mq_client
@msg_route(code = 203)
def TaobaoHandleDiscardInfo(dbname, uid, app_key, rsp):
    begin = datetime.datetime.fromtimestamp(rsp.packet.msg.begin/1000)
    end = datetime.datetime.fromtimestamp(rsp.packet.msg.end/1000)
    if begin >= end: return

    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
    top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
    cr.close()

    if begin.day < end.day:
        cut_time = datetime.datetime(begin.year, begin.month, begin.day, 23, 59, 59)
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"begin": int(time.mktime(begin.timetuple()) * 1000), "end": int(time.mktime(cut_time.timetuple())*1000)}, "code": 203}}
        TaobaoMsgRouter(dbname, uid, app_key, job)

        new_time = datetime.datetime(begin.year, begin.month, begin.day, 0, 0, 0) + datetime.timedelta(days=1)
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"begin": int(time.mktime(new_time.timetuple())*1000), "end": int(time.mktime(end.timetuple())*1000)}, "code": 203}}
        TaobaoMsgRouter(dbname, uid, app_key, job)
        return

    if (end - begin) > datetime.timedelta(hours = 1):
        cut_time = datetime.datetime(begin.year, begin.month, begin.day, begin.hour, 59, 59)
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"begin": int(time.mktime(begin.timetuple())*1000), "end": int(time.mktime(cut_time.timetuple())*1000)}, "code": 203}}
        TaobaoMsgRouter(dbname, uid, app_key, job)

        new_time = datetime.datetime(begin.year, begin.month, begin.day, begin.hour, 0, 0)  + datetime.timedelta(hours=1)
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"begin": int(time.mktime(new_time.timetuple())*1000), "end": int(time.mktime(end.timetuple())*1000)}, "code": 203}}
        TaobaoMsgRouter(dbname, uid, app_key, job)
        return

    tb_rsp = top('taobao.comet.discardinfo.get', user_id = shop.taobao_user_id, start = begin.strftime('%Y-%m-%d %H:%M:%S'), end = end.strftime('%Y-%m-%d %H:%M:%S'))

    if tb_rsp and tb_rsp.discard_info_list.has_key('discard_info'):
        discard_info_list = tb_rsp.discard_info_list.discard_info
        for discard_info in discard_info_list:
            page_no = 0
            page_size =  200
            total_results = 999
            while(total_results > page_no*page_size):
                method_name = 'taobao.increment.%ss.get' % str(discard_info.Type)
                start = datetime.datetime.fromtimestamp(discard_info.start/1000)
                end = datetime.datetime.fromtimestamp(discard_info.end/1000)
                notifys = []
                while start <= end:
                    if start.day == end.day:
                        notifys_rsp = top(method_name, nick = shop.taobao_nick, start_modified = start.strftime('%Y-%m-%d %H:%M:%S'), end_modified = end.strftime('%Y-%m-%d %H:%M:%S'),  page_no = page_no + 1, page_size = page_size)
                        start = datetime.datetime(start.year, start.month, start.day, 0, 0, 0)+ datetime.timedelta(days=1)
                        if notifys_rsp and notifys_rsp.get('notify_%ss' % str(discard_info.Type), None):
                            notifys += notifys_rsp['notify_%ss' % str(discard_info.Type)]['notify_%s' % str(discard_info.Type)]
                    elif start.day < end.day:
                        notifys_rsp = top(method_name, nick = shop.taobao_nick, start_modified = start.strftime('%Y-%m-%d %H:%M:%S'), page_no = page_no + 1, page_size = page_size)
                        start = datetime.datetime(start.year, start.month, start.day, 0, 0, 0)+ datetime.timedelta(days=1)
                        if notifys_rsp and notifys_rsp.get('notify_%ss' % str(discard_info.Type), None):
                            notifys += notifys_rsp['notify_%ss' % str(discard_info.Type)]['notify_%s' % str(discard_info.Type)]
                time.sleep(1/1000)

                for notify in notifys :
                    job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": notify, "code": 202}}
                    TaobaoMsgRouter(dbname, uid, app_key, job)

                total_results = int(notifys_rsp.total_results)
                page_no = page_no + 1

@mq_client
def TaobaoMsgRouter(dbname, uid, app_key, rsp, is_stream_data = False):
    _logger.info(rsp)

    if is_stream_data:
        try:
            pool = openerp.pooler.get_pool(dbname)
            cr = pool.db.cursor()
            pool.get('taobao.packet').create(cr, uid, {'taobao_app_key': app_key, 'data': rsp})
            cr.commit()
        finally:
            cr.close()

    try:
        if rsp.__class__ == dict:
            rsp = json.loads(json.dumps(rsp), strict=False, object_hook =lambda x: _O(x))
        elif rsp.__class__ == str or rsp.__class__ == unicode :
            rsp = json.loads(rsp, strict=False, object_hook =lambda x: _O(x))
    except:
        import traceback
        exc = traceback.format_exc()
        _logger.error(exc)
        return

    func = None
    keys = {}
    try:
        keys['code'] = rsp.packet.code
        tmp_func = STREAM_MSG_ROUTER.get(tuple(sorted(keys.items(), key=lambda x:x[0])), None)
        if tmp_func: func = tmp_func

        k,v = rsp.packet.msg.items()[0]
        keys['notify'] = str(k)
        tmp_func = STREAM_MSG_ROUTER.get(tuple(sorted(keys.items(), key=lambda x:x[0])), None)
        if tmp_func: func = tmp_func

        keys['status'] = str(v.status)
        tmp_func = STREAM_MSG_ROUTER.get(tuple(sorted(keys.items(), key=lambda x:x[0])), None)
        if tmp_func: func = tmp_func
    except:
        pass

    if func:func(dbname, uid, app_key, rsp)



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
