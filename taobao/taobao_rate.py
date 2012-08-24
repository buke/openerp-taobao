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
from taobao_base import TaobaoMixin
import datetime
import time
from .taobao_top import TOP
from crm import crm

class taobao_shop(osv.osv, TaobaoMixin):
    _inherit = "taobao.shop"
    _columns = {
            #taobao rate
            'enable_auto_check_rate': fields.boolean(u'自动检查中差评'),
            'rate_helpdesk_user_id': fields.many2one('res.users', u'默认负责人'),
            'rate_helpdesk_section_id': fields.many2one('crm.case.section', u'默认销售团队'),
            'rate_helpdesk_channel_id': fields.many2one('crm.case.channel', u'途径'),
            'rate_helpdesk_priority': fields.selection(crm.AVAILABLE_PRIORITIES, u'优先级'),
            'rate_helpdesk_categ_id': fields.many2one('crm.case.categ', 'Category', \
                            domain="['|',('section_id','=',False),('section_id','=',section_id),\
                            ('object_id.model', '=', 'crm.helpdesk')]"),
            'rate_remind_user': fields.boolean(u'发送邮件'),
            }

    _defaults = {
            'enable_auto_check_rate': True,
            }


class taobao_rate(osv.osv, TaobaoMixin):
    _name = "taobao.rate"
    _description = "Taobao Trade Rate"
    _columns = {
            'taobao_app_key': fields.char('App Key', size=256),
            'start_date': fields.char('Start Date', size=256),
            'end_date': fields.char('End Date', size=256),

            'name': fields.char(u'名字', size=256),
            'tid': fields.char(u'交易ID', size=256),
            'oid': fields.char(u'子订单ID', size=256),
            'valid_score': fields.boolean(u'评价信息是否用于记分'),
            'role': fields.selection([
                ('seller', u'卖家'),
                ('buyer', u'买家'),
                ],
                u'评价者角色',
                ),
            'nick': fields.char(u'评价者昵称', size=256),
            'result': fields.selection([
                ('good', u'好评'),
                ('neutral', u'中评'),
                ('bad', u'差评'),
                ],
                u'评价结果',
                ),
            'created': fields.datetime(u'评价创建时间'),
            'rated_nick': fields.char(u'被评价者昵称', size=256),
            'item_title': fields.char(u'商品标题', size=256),
            'item_price': fields.float(u'商品价格'),
            'content': fields.text(u'评价内容'),
            'reply': fields.text(u'评价解释'),
            }

    _sql_constraints = [('taobao_tid_oid_uniq','unique(tid, oid)', 'Taobao Order  must be unique!')]

    _order = 'id DESC'

    def _top_trade_rate_add(self, top, tid, result = 'good', role = 'seller', content = None, anony = False ):

        trade_fullinfo = self.pool.get('sale.order')._top_trade_fullinfo_get(top, tid)
        for order in trade_fullinfo.orders.order:
            top('taobao.traderate.add', tid = tid, oid = order.oid, result = result, role = role, content = content, anony = anony )

    def rate_ticket_new(self, cr, uid, shop, top, rate, remind_user = True):
        res_partner_obj = self.pool.get('res.partner')
        partner = res_partner_obj._get(cr, uid, args = [('taobao_nick','=',rate.nick)])
        if not partner:
            tbbuyer = res_partner_obj._top_user_get(top, nick=rate.nick)
            try:
                partner = res_partner_obj._save(cr, uid, args=[('taobao_nick','=', tbbuyer.nick), ('ref','=', '%s' % tbbuyer.nick)], **{'name':tbbuyer.nick, 'ref':'%s' % tbbuyer.nick, 'category_id': [shop.taobao_user_category_id.id], 'customer': True, 'taobao_user_id':tbbuyer.get('user_id', None), 'taobao_nick':tbbuyer.nick})
            except:
                #IntegrityError: duplicate key value violates unique constraint "res_partner_taobao_user_id_uniq"
                pass

        partner_address_id = res_partner_obj.address_get(cr, uid, [partner.id]).get('default', None)
        order = self.pool.get('sale.order')._get(cr, uid, args = [('taobao_trade_id','=',rate.tid)])
        desc = u"""
                买家昵称: %s
                卖家昵称: %s
                评价日期: %s
                评价类型: %s
                交易编号: %s
                子订单编号: %s
                商品标题: %s
                商品价格: %s
                评价内容: %s
               """ % (rate.nick, rate.rated_nick, rate.created, rate.result, rate.tid, rate.oid, rate.item_title, rate.item_price, rate.content )

        helpdesk_obj = self.pool.get('crm.helpdesk')
        helpdesk_id = helpdesk_obj.create(cr, uid, {
            'name': u'%s | %s | %s' % (rate.created, rate.nick, u'中评' if rate.result == 'neutral' else u'差评'),
            'active': True,
            'description': desc,
            'user_id': shop.rate_helpdesk_user_id.id,
            'section_id': shop.rate_helpdesk_section_id.id,
            'partner_id': partner.id,
            'partner_address_id':partner_address_id if partner_address_id else None,
            'ref' : '%s,%s' % ('sale.order', str(order.id)) if order else None,
            'channel_id': shop.rate_helpdesk_channel_id.id,
            'priority': shop.rate_helpdesk_priority,
            'categ_id': shop.rate_helpdesk_categ_id.id,
            })
        if remind_user: helpdesk_obj.remind_user(cr, uid, [helpdesk_id])

        cr.commit()


    def _top_traderates_get(self, top, start_date = None, end_date = None):
        rates = []
        #中评
        page_no = 0
        page_size = 50
        total_results = 999
        while(total_results > page_no*page_size):
            rsp =top('taobao.traderates.get', fields = ['tid','oid','role','nick','result','created','rated_nick','item_title','item_price','content','reply'], rate_type = 'get', role = 'buyer', result = 'neutral', start_date = start_date, end_date = end_date, page_no = page_no + 1, page_size = page_size)
            if rsp and rsp.get('trade_rates', False): rates = rates + rsp.trade_rates.trade_rate
            if rsp and rsp.has_key('total_results'):
                total_results = int(rsp.get('total_results', 0))
            else:
                total_results = 0
            page_no += 1
            time.sleep(1/1000)

        #差评
        page_no = 0
        page_size = 50
        total_results = 999
        while(total_results > page_no*page_size):
            rsp =top('taobao.traderates.get', fields = ['tid','oid','role','nick','result','created','rated_nick','item_title','item_price','content','reply'], rate_type = 'get', role = 'buyer', result = 'bad', start_date = start_date, end_date = end_date, page_no = page_no + 1, page_size = page_size)
            if rsp and rsp.get('trade_rates', False): rates = rates + rsp.trade_rates.trade_rate
            if rsp and rsp.has_key('total_results'):
                total_results = int(rsp.get('total_results', 0))
            else:
                total_results = 0
            page_no += 1
            time.sleep(1/1000)

        return rates


    def cron_check_rate(self, cr, uid, ids=False, context=None):
        shop_obj = self.pool.get('taobao.shop')
        shops = shop_obj.browse(cr, uid, shop_obj.search(cr, uid, []))
        for shop in shops:
            if not shop.enable_auto_check_rate: continue
            top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)

            end = datetime.datetime.utcnow() + datetime.timedelta(hours = 8)
            rate_ids = self.search(cr, uid, [('taobao_app_key','=', shop.taobao_app_key)], limit =1)
            if rate_ids and rate_ids[0]:
                start = datetime.datetime.strptime(self.browse(cr, uid, rate_ids[0]).end_date, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(seconds = 1)
            else:
                start = end - datetime.timedelta(days = 30)

            top_rates = self._top_traderates_get(top, start_date = start.strftime('%Y-%m-%d %H:%M:%S'), end_date = end.strftime('%Y-%m-%d %H:%M:%S'))
                #add ticket
            for rate in top_rates:
                self.rate_ticket_new(cr, uid, shop, top, rate, remind_user = shop.rate_remind_user)
                time.sleep(1)

            self.create(cr, uid, {
                'taobao_app_key': shop.taobao_app_key,
                'start_date': start.strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': end.strftime('%Y-%m-%d %H:%M:%S'),
                })

            time.sleep(1)



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
