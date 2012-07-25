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

from crm import crm
import openerp
from taobao_base import mq_client
from taobao_base import msg_route
from .taobao_top import TOP

class taobao_shop(osv.osv, TaobaoMixin):
    _inherit = "taobao.shop"
    _columns = {
            #taobao refund
            'enable_auto_check_refund': fields.boolean(u'检查退换货'),
            'refund_helpdesk_user_id': fields.many2one('res.users', u'默认负责人'),
            'refund_helpdesk_section_id': fields.many2one('crm.case.section', u'默认销售团队'),
            'refund_helpdesk_channel_id': fields.many2one('crm.case.channel', u'途径'),
            'refund_helpdesk_priority': fields.selection(crm.AVAILABLE_PRIORITIES, u'优先级'),
            'refund_helpdesk_categ_id': fields.many2one('crm.case.categ', 'Category', \
                            domain="['|',('section_id','=',False),('section_id','=',section_id),\
                            ('object_id.model', '=', 'crm.helpdesk')]"),
            'refund_remind_user': fields.boolean(u'发送邮件'),
            }

    _defaults = {
            }



class taobao_refund(osv.osv, TaobaoMixin):
    _name = "taobao.refund"
    _description = "Taobao Refund"
    _columns = {
            'name': fields.char(u'名字', size=256),
            'refund_id': fields.char(u'退款ID', size=256),
            'tid': fields.char(u'交易ID', size=256),
            'oid': fields.char(u'子订单ID', size=256),
            }

    def _top_refund_get(self, top, refund_id):
        rsp =top('taobao.refund.get', refund_id = refund_id, fields = ['refund_id', 'alipay_no', 'tid', 'oid', 'buyer_nick', 'seller_nick', 'total_fee', 'status', 'created', 'refund_fee', 'good_status', 'has_good_return', 'payment', 'reason', 'desc', 'num_iid', 'title', 'price', 'num', 'good_return_time', 'company_name', 'sid', 'address', 'shipping_type', 'refund_remind_timeout'])
        if rsp and rsp.get('refund', False):
            return rsp.refund
        else:
            return None

    def refund_ticket_new(self, cr, uid, shop, top, refund_id, remind_user = True):
        refund = self._top_refund_get(top, refund_id)
        if refund.seller_nick != shop.taobao_nick: return

        partner = self.pool.get('res.partner')._get(cr, uid, args = [('taobao_nick','=',refund.buyer_nick)])
        order = self.pool.get('sale.order')._get(cr, uid, args = [('taobao_trade_id','=',refund.tid)])
        if not (partner and order):
            self.pool.get('sale.order')._taobao_save_fullinfo(self.pool, cr, uid, refund.tid, shop, top)
            partner = self.pool.get('res.partner')._get(cr, uid, args = [('taobao_nick','=',refund.buyer_nick)])
            order = self.pool.get('sale.order')._get(cr, uid, args = [('taobao_trade_id','=',refund.tid)])

        partner_address_id = self.pool.get('res.partner').address_get(cr, uid, [partner.id]).get('default', None)
        desc = u"""
                退款ID: %s
                支付宝交易编号: %s
                交易编号: %s
                子订单编号: %s
                买家昵称: %s
                卖家昵称: %s
                交易总金额: ￥%s
                退款状态: %s
                退款日期: %s
                退款金额: %s
                货物状态: %s
                买家是否需要退货: %s
                支付给卖家的金额: %s
                退款原因: %s
                退款说明: %s
                申请退款的商品数字编号: %s
                商品标题: %s
                商品价格: %s
                商品购买数量: %s
               """ % (refund.refund_id, refund.alipay_no, refund.tid, refund.oid, refund.buyer_nick, refund.seller_nick, refund.total_fee, refund.status, refund.created, refund.refund_fee, refund.good_status, refund.has_good_return, refund.payment, refund.reason, refund.desc, refund.num_iid, refund.title, refund.price, refund.num)

        helpdesk_obj = self.pool.get('crm.helpdesk')
        helpdesk_id = helpdesk_obj.create(cr, uid, {
            'name': u'%s | %s | 退款编号:%s' % (refund.created, refund.buyer_nick, refund.refund_id),
            'active': True,
            'description': desc,
            'user_id': shop.refund_helpdesk_user_id.id,
            'section_id': shop.refund_helpdesk_section_id.id,
            'partner_id': partner.id,
            'partner_address_id':partner_address_id if partner_address_id else None,
            'ref' : '%s,%s' % ('sale.order', str(order.id)),
            'channel_id': shop.refund_helpdesk_channel_id.id,
            'priority': shop.refund_helpdesk_priority,
            'categ_id': shop.refund_helpdesk_categ_id.id,
            #'state': 'draft',
            })
        if remind_user: helpdesk_obj.remind_user(cr, uid, [helpdesk_id])
        cr.commit()


def TaobaoRefundSuccess(dbname, uid, app_key, rsp):
    #退款成功
    #TODO receive return goods or pay customer
    return

def TaobaoRefundClosed(dbname, uid, app_key, rsp):
    #退款关闭
    pass

@mq_client
@msg_route(code = 202, notify = 'notify_refund', status = 'RefundCreated')
def TaobaoRefundCreated(dbname, uid, app_key, rsp):
    #退款创建
    notify_refund = rsp.packet.msg.notify_refund
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        if shop.enable_auto_check_refund:
            top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
            pool.get('taobao.refund').refund_ticket_new(cr, uid, shop, top, notify_refund.refund_id, remind_user = shop.refund_remind_user)
            cr.commit()
    finally:
        cr.close()


def TaobaoRefundSellerAgreeAgreement(dbname, uid, app_key, rsp):
    #卖家同意退#款协议
    pass

def TaobaoRefundSellerRefuseAgreement(dbname, uid, app_key, rsp):
    #卖家拒绝退款协议
    pass

def TaobaoRefundBuyerModifyAgreement(dbname, uid, app_key, rsp):
    #买家修改退款协议
    pass

def TaobaoRefundBuyerReturnGoods(dbname, uid, app_key, rsp):
    #买家退货给卖家
    #TODO add carrier to incoming picking
    pass

def TaobaoRefundCreateMessage(dbname, uid, app_key, rsp):
    #发表退款留言
    pass

def TaobaoRefundBlockMessage(dbname, uid, app_key, rsp):
    #屏蔽退款留言
    pass

def TaobaoRefundTimeoutRemind(dbname, uid, app_key, rsp):
    #退款超时提醒
    #TODO send sms to customer?
    pass


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
