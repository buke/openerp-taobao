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
import logging
_logger = logging.getLogger(__name__)
from taobao_base import TaobaoMixin
from .taobao_top import TOP
import re
import datetime
import urllib

class taobao_shop(osv.osv, TaobaoMixin):
    _inherit = "taobao.shop"
    _columns = {
            'delivery_enable_sign_check': fields.boolean(u'检查快递签收情况'),
            'delivery_sign_reg': fields.text(u'签收标志', help = u'签收标志，使用正则表达式'),
            'delivery_sms_alert': fields.boolean(u'发送短信提醒买家确认', help = u'开发中...'),
            'delivery_sms_content': fields.text(u'短信内容', help = u'短信提醒内容'),

            'delivery_enable_remind_user': fields.boolean(u'发送邮件报告'),
            'delivery_emailto_user_id': fields.many2one('res.users', u'负责人'),

        }
    _defaults = {
            'delivery_enable_sign_check': True,
            'delivery_sign_reg': u'签收',
            'delivery_sms_alert': False,
            }


class stock_picking(osv.osv, TaobaoMixin):
    _inherit = 'stock.picking'

    _columns = {
        'carrier_tracking_state':fields.boolean(u'签收'),
        'carrier_tracking_detail': fields.text(u'物流详情'),
        }
    _defaults = {
            'carrier_tracking_state': False,
            }

    def _top_logistics_trace_search(self, top, tid, seller_nick):
        rsp =top('taobao.logistics.trace.search', tid=tid, seller_nick=seller_nick)
        return rsp if rsp else None

    def cron_check_carrier_tracking_state(self, cr, uid, ids=False, context=None):
        shop_obj = self.pool.get('taobao.shop')
        shops = shop_obj.browse(cr, uid, shop_obj.search(cr, uid, []))
        for shop in shops:
            if not shop.delivery_enable_sign_check: continue
            try:
                top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
                recmp = re.compile(shop.delivery_sign_reg)
                sql_req= """
                SELECT p.id as pid, so.taobao_trade_id as tid, tb.taobao_nick as nick
                FROM stock_picking p
                JOIN
                    sale_order so ON (p.sale_id = so.id)
                JOIN
                    taobao_shop tb ON (so.taobao_shop_id = tb.id)
                WHERE
                    so.taobao_trade_status = 'WAIT_BUYER_CONFIRM_GOODS'
                    AND p.carrier_tracking_state <> true
                    AND tb.id = %d
                """ % shop.id
                cr.execute(sql_req)
                pick_ids = [(x[0], x[1], x[2]) for x in cr.fetchall()]
                for pick_id, tb_tid, nick in pick_ids:
                    rsp = self._top_logistics_trace_search(top, tb_tid, nick)

                    trace_info = u'\r\n'.join([ u'%s %s' % (info.get('status_time', u''), info.get('status_desc', u'')) for info in rsp.trace_list.transit_step_info])

                    self.write(cr, uid, pick_id, {
                        'carrier_tracking_state': True if recmp.search(trace_info) else False,
                        'carrier_tracking_detail': trace_info,
                        })
            except:
                import traceback
                exc = traceback.format_exc()
                _logger.error(exc)


    def cron_carrier_tracking_remind(self, cr, uid, ids=False, context=None):
        shop_obj = self.pool.get('taobao.shop')
        shops = shop_obj.browse(cr, uid, shop_obj.search(cr, uid, []))
        for shop in shops:
            sms_reminds = {}
            email_body_lines = []
            try:
                sql_req= """
                SELECT p.id as pid
                FROM stock_picking p
                JOIN
                    sale_order so ON (p.sale_id = so.id)
                JOIN
                    taobao_shop tb ON (so.taobao_shop_id = tb.id)
                WHERE
                    so.taobao_trade_status = 'WAIT_BUYER_CONFIRM_GOODS'
                    AND p.carrier_tracking_state = true
                    AND tb.id = %d
                ORDER BY p.partner_id
                """ % shop.id
                cr.execute(sql_req)
                rep = [x[0] for x in cr.fetchall()]
                if not rep: continue
                pickings = self.browse(cr, uid, rep)
                for picking in pickings:
                    if  shop.delivery_sms_alert and shop.delivery_sms_content.strip() and picking.partner_id.taobao_receive_sms_remind:
                        sms_reminds[picking.address_id.mobile] = shop.delivery_sms_content.strip()

                    if shop.delivery_enable_remind_user:
                        email_body_lines.append((
                            picking.partner_id.taobao_nick,
                            picking.sale_id.taobao_trade_id,
                            picking.carrier_id.name,
                            picking.carrier_tracking_ref,
                            picking.carrier_tracking_detail,
                            picking.address_id.taobao_full_address
                            ))

                #send sms
                if sms_reminds:
                    pass

                if email_body_lines:
                    lines = []
                    for nick, tid, kuaidi, num, info, address  in email_body_lines:
                        line = u"""
                        <tr>
                            <td>
                                <a target="_blank" href="http://www.taobao.com/webww/ww.php?ver=3&touid=%s&siteid=cntaobao&status=1&charset=utf-8"><img border="0" src="http://amos.alicdn.com/realonline.aw?v=2&uid=%s&site=cntaobao&s=1&charset=utf-8" alt="点击这里给我发消息" /></a>
                            </td>
                            <td><a target="_blank" href="http://trade.taobao.com/trade/detail/trade_item_detail.htm?bizOrderId=%s">%s</a></td>
                            <td>%s:%s</td>
                            <td width=50%%>%s</td>
                            <td>%s</td>
                        </tr>
                        """ % ( urllib.quote(nick.encode('utf8')), urllib.quote(nick.encode('utf8')),
                                tid, tid,
                                kuaidi, num,
                                info.replace(u'\r\n', u'<br/>'),
                                address,
                                )
                        lines.append(line)

                    body = u"""
                    <table border="1">
                        <tr>
                            <td>旺旺</td><td>淘宝订单</td><td>快递</td><td width=50%%>物流跟踪</td><td>地址</td>
                        </tr>
                        %s
                    </table>
                    """ % u''.join(lines)

                    now = datetime.datetime.utcnow() + datetime.timedelta(hours = 8)
                    subject = u'%s | %s | %d个订单 已签收未确认' % (now.strftime('%Y-%m-%d'), shop.taobao_nick, len(email_body_lines))
                    self.pool.get('mail.message').schedule_with_attach(cr, uid, shop.delivery_emailto_user_id.user_email, [shop.delivery_emailto_user_id.user_email], subject, body, subtype='html',)

            except:
                import traceback
                exc = traceback.format_exc()
                _logger.error(exc)












# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
