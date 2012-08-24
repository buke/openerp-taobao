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

from ..taobao_top import TOP
from osv import fields, osv
import datetime
import time
from ..taobao_shop import TaobaoMsgRouter

class taobao_order_import_line(osv.osv_memory):
    _name = "taobao.order.import.line"
    _description = "Taobao Order Import Line"
    _columns = {
            'tid': fields.char(u'淘宝交易编号', size = 64),
            'taobao_shop_id': fields.many2one('taobao.shop', 'Taobao Shop', required=True),
            'status': fields.selection([
                ('TRADE_NO_CREATE_PAY', u'没有创建支付宝交易'),
                ('WAIT_BUYER_PAY', u'等待买家付款'),
                ('WAIT_SELLER_SEND_GOODS', u'买家已付款,等待卖家发货'),
                ('WAIT_BUYER_CONFIRM_GOODS', u'卖家已发货,等待买家确认收货'),
                ('TRADE_BUYER_SIGNED', u'买家已签收,货到付款专用'),
                ('TRADE_FINISHED', u'交易成功'),
                ('TRADE_CLOSED', u'付款以后用户退款成功，交易自动关闭'),
                ('TRADE_CLOSED_BY_TAOBAO', u'付款以前，卖家或买家主动关闭交易')
                ],
                u'交易状态'),
            'buyer_nick': fields.char(u'买家', size = 128),
            'total_fee': fields.char(u'总价', size = 128),
            'pay_time': fields.char(u'付款时间', size = 128),
            'wizard_id' : fields.many2one('taobao.order.import', string="Wizard"),
            }

class taobao_order_import(osv.osv_memory):
    _name = "taobao.order.import"
    _description = "Import Taobao Order"
    _columns = {
            'taobao_shop_id': fields.many2one('taobao.shop', 'Taobao Shop', required=True),
            'order_time': fields.selection([
                (1, u'最近一天'),
                (3, u'最近三天'),
                (7, u'最近一周'),
                (15, u'最近半个月'),
                (30, u'最近一个月'),
                (90, u'最近三个月'),
                ],
                u'时间过滤', required=True),
            'TRADE_NO_CREATE_PAY': fields.boolean(u'没有创建支付宝交易'),
            'WAIT_BUYER_PAY': fields.boolean(u'等待买家付款'),
            'WAIT_SELLER_SEND_GOODS': fields.boolean(u'买家已付款,等待卖家发货'),
            'WAIT_BUYER_CONFIRM_GOODS': fields.boolean(u'卖家已发货,等待买家确认收货'),
            'TRADE_BUYER_SIGNED': fields.boolean(u'买家已签收,货到付款专用'),
            'TRADE_FINISHED': fields.boolean(u'交易成功'),
            'TRADE_CLOSED': fields.boolean(u'付款以后用户退款成功，交易自动关闭'),
            'TRADE_CLOSED_BY_TAOBAO': fields.boolean(u'付款以前，卖家或买家主动关闭交易'),

            'order_import_lines' : fields.one2many('taobao.order.import.line', 'wizard_id', u'淘宝产品列表'),
            }
    _defaults = {
            'order_time': 7,
            'WAIT_SELLER_SEND_GOODS': True,
            'WAIT_BUYER_CONFIRM_GOODS': True,
            }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(taobao_order_import, self).default_get(cr, uid, fields, context=context)


        if 'order_import_lines' in fields and context.has_key('order_import_lines'):
            res.update({'order_import_lines': context['order_import_lines']})

        if 'order_time' in fields and context.has_key('order_time'):
            res.update({'order_time': context['order_time']})

        if 'taobao_shop_id' in fields:
            if context.get('taobao_shop_id', False):
                res.update({'taobao_shop_id': context['taobao_shop_id']})
            else:
                active_model = context.get('active_model', False)
                active_ids = context.get('active_ids', False)
                if active_model == 'taobao.shop' and active_ids:
                    taobao_shop = self.pool.get('taobao.shop').browse(cr, uid, active_ids[0], context=context)
                    if taobao_shop: res.update({'taobao_shop_id':taobao_shop.id})
                if active_model == 'sale.order' and active_ids:
                    sale_orders = self.pool.get('sale.order').browse(cr, uid, active_ids, context=context)
                    lines = []
                    for order in sale_orders:
                        taobao_shop = order.taobao_shop_id
                        lines.append({
                            'tid': order.taobao_trade_id ,
                            'taobao_shop_id': order.taobao_shop_id.id ,
                            })
                        res.update({'taobao_shop_id':order.taobao_shop_id.id})
                    res.update({'order_import_lines': lines})

        if 'TRADE_NO_CREATE_PAY' in fields and context.has_key('TRADE_NO_CREATE_PAY'):
            res.update({'TRADE_NO_CREATE_PAY': context['TRADE_NO_CREATE_PAY']})
        if 'WAIT_BUYER_PAY' in fields and context.has_key('WAIT_BUYER_PAY'):
            res.update({'WAIT_BUYER_PAY': context['WAIT_BUYER_PAY']})
        if 'WAIT_SELLER_SEND_GOODS' in fields and context.has_key('WAIT_SELLER_SEND_GOODS'):
            res.update({'WAIT_SELLER_SEND_GOODS': context['WAIT_SELLER_SEND_GOODS']})
        if 'WAIT_BUYER_CONFIRM_GOODS' in fields and context.has_key('WAIT_BUYER_CONFIRM_GOODS'):
            res.update({'WAIT_BUYER_CONFIRM_GOODS': context['WAIT_BUYER_CONFIRM_GOODS']})
        if 'TRADE_BUYER_SIGNED' in fields and context.has_key('TRADE_BUYER_SIGNED'):
            res.update({'TRADE_BUYER_SIGNED': context['TRADE_BUYER_SIGNED']})
        if 'TRADE_FINISHED' in fields and context.has_key('TRADE_FINISHED'):
            res.update({'TRADE_FINISHED': context['TRADE_FINISHED']})
        if 'TRADE_CLOSED' in fields and context.has_key('TRADE_CLOSED'):
            res.update({'TRADE_CLOSED': context['TRADE_CLOSED']})
        if 'TRADE_CLOSED_BY_TAOBAO' in fields and context.has_key('TRADE_CLOSED_BY_TAOBAO'):
            res.update({'TRADE_CLOSED_BY_TAOBAO': context['TRADE_CLOSED_BY_TAOBAO']})
        return res


    def search_order(self, cr, uid, ids, context=None):
        if ids and ids[0]:
            order_import = self.browse(cr, uid, ids[0], context=context)
            context['taobao_shop_id'] = order_import.taobao_shop_id.id
            context['TRADE_NO_CREATE_PAY'] = order_import.TRADE_NO_CREATE_PAY
            context['WAIT_BUYER_PAY'] = order_import.WAIT_BUYER_PAY
            context['WAIT_SELLER_SEND_GOODS'] = order_import.WAIT_SELLER_SEND_GOODS
            context['WAIT_BUYER_CONFIRM_GOODS'] = order_import.WAIT_BUYER_CONFIRM_GOODS
            context['TRADE_BUYER_SIGNED'] = order_import.TRADE_BUYER_SIGNED
            context['TRADE_FINISHED'] = order_import.TRADE_FINISHED
            context['TRADE_CLOSED'] = order_import.TRADE_CLOSED
            context['TRADE_CLOSED_BY_TAOBAO'] = order_import.TRADE_CLOSED_BY_TAOBAO

            order_status = []
            if order_import.TRADE_NO_CREATE_PAY: order_status.append('TRADE_NO_CREATE_PAY')
            if order_import.WAIT_BUYER_PAY: order_status.append('WAIT_BUYER_PAY')
            if order_import.WAIT_SELLER_SEND_GOODS: order_status.append('WAIT_SELLER_SEND_GOODS')
            if order_import.WAIT_BUYER_CONFIRM_GOODS: order_status.append('WAIT_BUYER_CONFIRM_GOODS')
            if order_import.TRADE_BUYER_SIGNED: order_status.append('TRADE_BUYER_SIGNED')
            if order_import.TRADE_FINISHED: order_status.append('TRADE_FINISHED')
            if order_import.TRADE_CLOSED: order_status.append('TRADE_CLOSED')
            if order_import.TRADE_CLOSED_BY_TAOBAO: order_status.append('TRADE_CLOSED_BY_TAOBAO')

            shop = order_import.taobao_shop_id
            top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)

            context['order_time'] = order_import.order_time
            if order_import.order_time == 90:
                taobao_orders = self.pool.get('sale.order')._top_sold_get(top, order_status)
            else:
                now = datetime.datetime(*tuple(time.gmtime())[:6]) + datetime.timedelta(hours=8)
                end_created = now.strftime('%Y-%m-%d %H:%M:%S')
                start_created = (now - datetime.timedelta(days=order_import.order_time)).strftime('%Y-%m-%d %H:%M:%S')
                taobao_orders = self.pool.get('sale.order')._top_sold_get(top, order_status, start_created = start_created, end_created = end_created)

            for i in range(len(taobao_orders)):
                taobao_orders[i]['taobao_shop_id'] = order_import.taobao_shop_id.id

            context['order_import_lines'] = taobao_orders

        return {
                'name': 'Import Product',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'taobao.order.import',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': context
                }


    def import_order(self, cr, uid, ids, context=None):
        if ids and ids[0]:
            order_import = self.browse(cr, uid, ids[0], context=context)

            for line in order_import.order_import_lines:
                shop = line.taobao_shop_id
                job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"import_taobao_order":{"tid": line.tid, "status": line.status if line.status else None }}, "code": 9999}}
                TaobaoMsgRouter(cr.dbname, uid, shop.taobao_app_key, job)


        return {
                'type': 'ir.actions.act_window_close',
                }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
