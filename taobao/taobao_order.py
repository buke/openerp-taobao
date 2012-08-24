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
import time
import netsvc
from .taobao_top import TOP
import openerp
from openerp.osv.osv import except_osv
from taobao_base import TaobaoMixin
from taobao_base import mq_client
from taobao_base import msg_route
import logging
_logger = logging.getLogger(__name__)


class taobao_shop(osv.osv, TaobaoMixin):
    _inherit = "taobao.shop"
    _columns = {
            #taobao order
            'enable_auto_rate': fields.boolean(u'交易成功自动评价'),
            'taobao_rate_content': fields.text(u'评价内容'),
            'taobao_journal_id':fields.many2one('account.journal', 'Journal', select=1, required=True),
            }
    _defaults = {
            'enable_auto_rate': True,
            }


class account_voucher(osv.osv, TaobaoMixin):
    _inherit = "account.voucher"

class sale_order_line(osv.osv, TaobaoMixin):
    _inherit = "sale.order.line"
    _columns = {
            'taobao_order_id': fields.char(u'淘宝订单编号', size = 64),
            }

    _sql_constraints = [('taobao_order_id_uniq','unique(taobao_order_id)', 'Taobao Order must be unique!')]



class sale_order(osv.osv, TaobaoMixin):
    _inherit = "sale.order"

    def _get_taobao_trade_url(self, cr, uid, ids, field_name, arg, context=None):
        res = {}

        for trade in self.browse(cr, uid, ids, context=context):
            res[trade.id] = 'http://trade.taobao.com/trade/detail/trade_item_detail.htm?bizOrderId=%s' % trade.taobao_trade_id if trade.taobao_trade_id else None

        return res

    _columns = {
            'taobao_shop_id': fields.many2one('taobao.shop', 'Taobao Shop', select=True),
            'taobao_trade_id': fields.char(u'淘宝交易编号', size = 64),
            'taobao_pay_time': fields.char(u'淘宝付款时间', size = 64),
            'taobao_alipay_no': fields.char(u'支付宝交易编号', size = 64),
            'taobao_trade_url': fields.function(_get_taobao_trade_url, type='char', string=u'淘宝订单信息'),
            'taobao_trade_status': fields.selection([
                ('TRADE_NO_CREATE_PAY', u'没有创建支付宝交易'),
                ('WAIT_BUYER_PAY', u'等待买家付款'),
                ('WAIT_SELLER_SEND_GOODS', u'买家已付款,等待卖家发货'),
                ('WAIT_BUYER_CONFIRM_GOODS', u'卖家已发货,等待买家确认收货'),
                ('TRADE_BUYER_SIGNED', u'买家已签收,货到付款专用'),
                ('TRADE_FINISHED', u'交易成功'),
                ('TRADE_CLOSED', u'付款以后用户退款成功，交易自动关闭'),
                ('TRADE_CLOSED_BY_TAOBAO', u'付款以前，卖家或买家主动关闭交易')
                ],
                u'淘宝交易状态'),

            'taobao_buyer_message': fields.text(u'买家留言'),
            'taobao_seller_memo': fields.text(u'卖家备注'),
            }

    _sql_constraints = [('taobao_trade_id_uniq','unique(taobao_trade_id)', 'Taobao Trade must be unique!')]

    def _top_sold_get(self, top, order_status, start_created = None,  end_created = None):

        trades = []
        for status in order_status:
            page_no = 0
            page_size = 50
            total_results = 999
            while(total_results > page_no*page_size):
                if start_created and end_created:
                    rsp =top('taobao.trades.sold.get', start_created=start_created, end_created=end_created, status=status,  fields = ['tid', 'status', 'buyer_nick', 'total_fee', 'pay_time'], page_no = page_no + 1, page_size = page_size)
                else:
                    rsp =top('taobao.trades.sold.get', status=status,  fields = ['tid', 'status', 'buyer_nick', 'total_fee', 'pay_time'], page_no = page_no + 1, page_size = page_size)

                if rsp and  rsp.has_key('trades'): trades = trades + rsp.trades.trade
                total_results = int(rsp.total_results)
                page_no += 1
                time.sleep(1/1000)

        return trades


    def _top_trade_fullinfo_get(self, top, tid):
        rsp =top('taobao.trade.fullinfo.get', tid=tid, fields=[
            'seller_nick', 'buyer_nick', 'title', 'type', 'created',
            'tid', 'seller_rate', 'buyer_flag', 'buyer_rate', 'status',
            'payment', 'adjust_fee', 'post_fee', 'total_fee', 'pay_time',
            'end_time', 'modified', 'consign_time', 'buyer_obtain_point_fee',
            'point_fee', 'real_point_fee', 'received_payment', 'commission_fee',
            'buyer_memo', 'seller_memo', 'alipay_no', 'alipay_id','is_brand_sale',
            'buyer_message', 'pic_path', 'num_iid', 'num', 'price',
            'buyer_alipay_no', 'receiver_name', 'receiver_state', 'receiver_city',
            'receiver_district', 'receiver_address', 'receiver_zip', 'receiver_mobile',
            'receiver_phone', 'buyer_email', 'seller_flag', 'seller_alipay_no',
            'seller_mobile', 'seller_phone', 'seller_name', 'seller_email',
            'available_confirm_fee', 'has_post_fee', 'timeout_action_time',
            'snapshot_url', 'cod_fee', 'cod_status', 'shipping_type', 'trade_memo',
            'is_3D', 'buyer_area', 'trade_from', 'is_lgtype', 'is_force_wlb',
            'orders',
            'promotion_details',
            ])

        if rsp and rsp.get('trade', None):
            return rsp.trade
        else:
            return None

    def _taobao_save_fullinfo(self, pool, cr, uid, taobao_trade_id, shop, top, context=None):
        trade_fullinfo = self._top_trade_fullinfo_get(top, taobao_trade_id)
        if trade_fullinfo.get('seller_nick', None) != shop.taobao_nick:
            return None

        #保存 res.partner
        res_partner_obj = pool.get('res.partner')
        tbbuyer = res_partner_obj._top_user_get(top, nick=trade_fullinfo.buyer_nick)
        partner = res_partner_obj._save(cr, uid, args=[('taobao_nick','=', tbbuyer.nick), ('ref','=', '%s' % tbbuyer.nick)], **{'name':tbbuyer.nick, 'ref':'%s' % tbbuyer.nick, 'category_id': [shop.taobao_user_category_id.id], 'customer': True, 'taobao_user_id':tbbuyer.get('user_id', None), 'taobao_nick':tbbuyer.nick})

        #保存 res.partner.address
        res_partner_address_obj = pool.get('res.partner.address')
        vals = {}
        vals['partner_id'] = partner.id
        vals['type'] = 'default'
        vals['name'] = trade_fullinfo.get('receiver_name', '')
        vals['phone'] = trade_fullinfo.get('receiver_phone', '')
        vals['mobile'] = trade_fullinfo.get('receiver_mobile', '')
        vals['receiver_state'] = trade_fullinfo.get('receiver_state', '')
        state_ids = pool.get('res.country.state').search(cr, uid, [('name','=',trade_fullinfo.get('receiver_state', ''))])
        if state_ids: vals['state_id'] = state_ids[0]

        vals['city'] = trade_fullinfo.get('receiver_city', '')
        street = trade_fullinfo.get('receiver_district', '') + ' ' + trade_fullinfo.get('receiver_address','')
        vals['street'] = street[0:64]
        vals['street2'] = street[64:128]
        vals['zip'] =trade_fullinfo.get('receiver_zip', '')

        vals['buyer_alipay_no'] = trade_fullinfo.get('buyer_alipay_no', '')
        if vals['buyer_alipay_no'].find('@') > -1:
            vals['email'] = vals['buyer_alipay_no']

        vals['taobao_full_address'] = ','.join([vals['name'], vals['phone'], vals['mobile'], vals['receiver_state'], street, vals['zip']])

        country_id = pool.get('res.country').search(cr, uid, [('code','=','CN')])[0]
        vals['country_id'] = country_id
        partner_address = res_partner_address_obj._save(cr, uid, args=[
            ('taobao_full_address','=',vals['taobao_full_address']),
            ], **vals)

        # 保存支付宝帐号
        trade_fullinfo['buyer_alipay_no'] = trade_fullinfo.get('buyer_alipay_no', '')
        if trade_fullinfo['buyer_alipay_no']:
            vals = {}
            vals['acc_number'] = trade_fullinfo.buyer_alipay_no
            vals['bank'] = pool.get('res.bank').search(cr, uid, args=[('bic','=', 'alipay')])[0]
            vals['bank_bic'] = 'alipay'
            vals['bank_name'] = u'支付宝'
            vals['owner_name'] = tbbuyer.nick
            vals['partner_id'] = partner.id
            vals['state'] = 'alipay'
            pool.get('res.partner.bank')._save(cr, uid, args=[('acc_number','=', trade_fullinfo.buyer_alipay_no)], **vals)

        vals = {}
        #保存 sale.order
        vals['taobao_shop_id'] = shop.id
        vals['taobao_trade_id'] = trade_fullinfo.tid
        vals['taobao_pay_time'] = trade_fullinfo.get('pay_time', None)
        vals['taobao_alipay_no'] = trade_fullinfo.get('alipay_no', None)
        vals['taobao_trade_status'] = trade_fullinfo.status
        vals['name'] = 'TB%s' % trade_fullinfo.tid
        vals['shop_id'] = shop.sale_shop_id.id
        vals['origin'] = 'TB%s' % trade_fullinfo.tid
        vals['client_order_ref'] = 'TB%s' % trade_fullinfo.tid
        if context and context.get('order_state', None):
            vals['state'] = context.get('order_state', None)
        vals['pricelist_id'] = shop.sale_shop_id.pricelist_id.id
        vals['partner_id'] = partner.id
        vals['partner_invoice_id'] = partner_address.id
        vals['partner_order_id'] = partner_address.id
        vals['partner_shipping_id'] = partner_address.id
        vals['taobao_buyer_message'] = trade_fullinfo.get('buyer_message', '')
        vals['taobao_seller_memo'] = trade_fullinfo.get('seller_memo', '')

        sale_order_instance = self._save(cr, uid, args=[('origin','=','TB%s' % taobao_trade_id)], **vals)

        #保存 sale.order.line
        sale_order_line_obj = pool.get('sale.order.line')
        for order in trade_fullinfo.orders.order:
            product = pool.get('taobao.product')._get_create_product(
                    pool, cr, uid, shop, top,
                    taobao_num_iid = order.get('num_iid', None),
                    taobao_sku_id = order.get('sku_id', None),
                    )

            #TRADE_CLOSED(付款以后用户退款成功，交易自动关闭)
            #TRADE_CLOSED_BY_TAOBAO(付款以前，卖家或买家主动关闭交易)
            if order.status in ['TRADE_CLOSED']:
                sol = sale_order_line_obj._get(cr, uid, args = [('taobao_order_id','=', order.oid)])
                if sol : pool.get('sale.order.line').unlink(cr, uid, [sol.id])
                continue

            vals = {}
            vals['order_id'] = sale_order_instance.id
            order['num_iid'] = order.get('num_iid', None)
            order['sku_id'] = order.get('sku_id', None)
            vals['product_id'] = product.id
            vals['name'] = '[%s] %s' % (product.default_code, product.name)
            vals['taobao_order_id'] = order.oid
            vals['product_uom_qty'] = int(order.num)
            vals['price_unit'] = float(order.total_fee) / float(order.num)
            vals['delay'] = 30.0
            sale_order_line_obj._save(cr, uid, args=[('taobao_order_id','=', order.oid)], **vals)

        #保存邮费
        post_fee = float(trade_fullinfo.get('cod_fee', '0')) + float(trade_fullinfo.get('post_fee', '0'))
        product_product_obj = pool.get('product.product')
        post_product = product_product_obj._get(cr, uid, args=[('default_code', '=', 'post_fee')])

        if post_fee > 0 and bool(trade_fullinfo.get('has_post_fee', True)):
            vals = {}
            vals['order_id'] = sale_order_instance.id
            vals['product_id'] = post_product.id
            vals['name'] = '[%s] %s' % (post_product.default_code, post_product.name)
            vals['product_uom_qty'] = 1
            vals['price_unit'] = post_fee
            vals['sequence'] = 100
            sale_order_line_obj._save(cr, uid, args=[('order_id','=', sale_order_instance.id), ('product_id','=', post_product.id)], **vals)
        else:
            post_line = sale_order_line_obj._get(cr, uid, args=[('order_id','=', sale_order_instance.id), ('product_id','=', post_product.id)])
            if post_line:
                sale_order_line_obj._save(cr, uid, ids=[post_line.id], **{'state':'cancel'})
                sale_order_line_obj.unlink(cr, uid, [post_line.id])

        cr.commit()

        return sale_order_instance

    def _taobao_confirm_order(self, pool, cr, uid, ids):
        #confirm order
        for sale_id in ids:
            sale_order_obj = pool.get('sale.order')
            sale_order_instance = sale_order_obj.browse(cr, uid, sale_id)
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, "sale.order", sale_id, 'order_confirm', cr)

            picking_ids = map(lambda x: x.id, sale_order_instance.picking_ids)

            for picking_id in picking_ids:
                wf_service.trg_validate(uid, "stock.picking", picking_id, 'button_confirm', cr)

            for line in  sale_order_obj.procurement_lines_get(cr, uid, [sale_id]):
                wf_service.trg_validate(uid, "procurement.order", line, 'button_confirm', cr)

            picking_obj = pool.get('stock.picking')
            try:
                picking_obj.action_assign(cr, uid, picking_ids)
            except except_osv: #('Warning !', 'Not enough stock, unable to reserve the products.')
                picking_obj.force_assign(cr, uid, picking_ids)
            except:
                import traceback
                exc = traceback.format_exc()
                _logger.error(exc)

        cr.commit()

    def _taobao_cancel_order(self, pool, cr, uid, ids):
        for sale_id in ids:
            wf_service = netsvc.LocalService("workflow")
            sale_order_instance = self.browse(cr, uid, sale_id)
            picking_ids = map(lambda x: x.id, sale_order_instance.picking_ids)

            for picking_id in picking_ids:
                wf_service.trg_validate(uid, "stock.picking", picking_id, 'button_cancel', cr)

            invoice_ids = map(lambda x: x.id, sale_order_instance.invoice_ids)
            for inv in invoice_ids:
                wf_service.trg_validate(uid, 'account.invoice', inv, 'invoice_cancel', cr)

            self.action_cancel(cr, uid, [sale_id])

        cr.commit()

    def _taobao_reopen_order(self, pool, cr, uid, ids):
        self._save(cr, uid, ids = ids, **{'state':'draft'})
        cr.commit()

    def _taobao_order_ship(self, pool, cr, uid, ids, top):
        for sale_id in ids:
            wf_service = netsvc.LocalService("workflow")
            sale_order_instance = self.browse(cr, uid, sale_id)
            if (not sale_order_instance) or int(sale_order_instance.picked_rate) == 100: continue
            picking_obj = pool.get('stock.picking')
            picking_ids = map(lambda x: x.id, sale_order_instance.picking_ids)

            for picking_id in picking_ids:
                context = dict({'date':time.strftime('%Y-%m-%d')}, active_ids=picking_ids, active_model='stock.picking')
                partial_id = pool.get("stock.partial.picking").create(cr, uid, {'picking_id':picking_id, 'date':time.strftime('%Y-%m-%d')}, context=context)
                pool.get('stock.partial.picking').do_partial(cr, uid, [partial_id], context=context)

            #add carrier to picking
            ship_data = self._taobao_get_ship(top, sale_order_instance.taobao_trade_id)
            if not ship_data: continue
            try:
                carrier_id = pool.get('delivery.carrier').search(cr, uid, args=[('name','=', ship_data['company_name'])])[0]
            except:
                carrier_id = pool.get('delivery.carrier').write(cr, uid, {
                    'name': ship_data['company_name'],
                    'partner_id': pool.get('delivery.carrier').search(cr, uid, args=[('name','=', u'快递')])[0],
                    'product_id': pool.get('product.product').search(cr, uid, args=[('default_code','=', 'post_fee')])[0],
                    })

            carrier_tracking_ref = ship_data['out_sid']
            picking_obj.write(cr, uid, picking_ids, {
                'carrier_id': carrier_id,
                'carrier_tracking_ref': carrier_tracking_ref,
                })


            for line in  self.procurement_lines_get(cr, uid, [sale_id]):
                wf_service.trg_validate(uid, "procurement.order", line, 'button_check', cr)

            for picking_id in picking_ids:
                wf_service.trg_validate(uid, "stock.picking", picking_id, 'button_done', cr)

        cr.commit()

    def _taobao_create_invoice(self, pool, cr, uid, ids):
        for sale_id in ids:
            wf_service = netsvc.LocalService("workflow")
            sale_order_instance = self.browse(cr, uid, sale_id)
            self.manual_invoice(cr, uid, [sale_order_instance.id])
            invoice_ids = pool.get('account.invoice').search(cr, uid, [('origin','=',sale_order_instance.origin)])
            for invoice_id in invoice_ids:
                wf_service.trg_validate(uid, "account.invoice", invoice_id, 'invoice_open', cr)
        cr.commit()

    def _taobao_get_ship(self, top, taobao_trade_id):
        try:
            rsp =top('taobao.logistics.orders.detail.get', tid=taobao_trade_id, fields = ['order_code', 'out_sid', 'company_name'])
            return {
                    'company_name' : rsp.shippings.shipping[0].company_name,
                    'out_sid' : rsp.shippings.shipping[0].out_sid,
                    'order_code' : rsp.shippings.shipping[0].order_code,
                    }
        except:
            return None

    def _taobao_pay_invoice(self, pool, cr, uid, shop, ids):
        for sale_id in ids:
            sale_order_instance = self.browse(cr, uid, sale_id)
            invoice_ids = pool.get('account.invoice').search(cr, uid, [('origin','=',sale_order_instance.origin)])
            for invoice_id in invoice_ids:
                inv = pool.get('account.invoice').browse(cr, uid, invoice_id)
                account_voucher_obj = pool.get('account.voucher')
                context = {
                    'partner_id' : inv.partner_id.id,
                    'journal_id' : shop.taobao_journal_id.id,
                    'company_id' : shop.taobao_journal_id.company_id.id,
                    'account_id' : shop.taobao_journal_id.default_credit_account_id and shop.taobao_journal_id.default_credit_account_id.id or False,
                    'account_id': shop.taobao_journal_id.default_credit_account_id and shop.taobao_journal_id.default_credit_account_id.id or False,
                    'period_id': account_voucher_obj._get_period(cr, uid),
                    'payment_option': 'without_writeoff',
                    'amount': inv.residual,
                    'comment': 'Write-Off',
                    'reference': 'AL%s' % sale_order_instance.taobao_alipay_no if sale_order_instance.taobao_alipay_no else None,
                    'date': time.strftime('%Y-%m-%d'),
                    'type': inv.type in ('out_invoice','out_refund') and 'receipt' or 'payment',
                        }
                context.update(account_voucher_obj.onchange_journal(cr, uid, [], context['journal_id'], [],  account_voucher_obj._get_tax(cr, uid, context=context), context['partner_id'],  context['date'], context['amount'], context['type'], context['company_id'],context=context)['value'])

                context['line_dr_ids'] =  [[5, False, False]] + [[0, False,line_id] for line_id in context['line_dr_ids']] if context['line_dr_ids'] else []
                context['line_cr_ids'] =  [[5, False, False]] + [[0, False,line_id] for line_id in context['line_cr_ids']] if context['line_cr_ids'] else []
                context['line_ids'] =  [[5, False, False]] + [[0, False,line_id] for line_id in context['line_ids']] if context['line_ids'] else []

                context.update(account_voucher_obj.onchange_line_ids(cr, uid, [], context['line_dr_ids'], context['line_cr_ids'], context['amount'], shop.taobao_journal_id.currency.id, context=context)['value'])

                account_voucher_instance = account_voucher_obj._save(cr, uid, **context)
                account_voucher_obj.proforma_voucher(cr, uid, [account_voucher_instance.id], context=context)

        cr.commit()

@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeAlipayCreate')
def TaobaoTradeAlipayCreate(dbname, uid, app_key, rsp):
    #创建支付宝交易
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        cr.commit()
    finally:
        cr.close()


@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeCreate')
def TaobaoTradeCreate(dbname, uid, app_key, rsp):
    #创建交易
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        cr.commit()
    finally:
        cr.close()


@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeModifyFee')
def TaobaoTradeModifyFee(dbname, uid, app_key, rsp):
    #修改交易费用
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        cr.commit()
    finally:
        cr.close()



@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeCloseAndModifyDetailOrder')
def TaobaoTradeCloseAndModifyDetailOrder(dbname, uid, app_key, rsp):
    #关闭或修改子订单
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_obj._taobao_cancel_order(pool, cr, uid, sale_order_obj.search(cr, uid, [('origin','=','TB%s' % notify_trade.tid)]))
        sale_order_instance = sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        if sale_order_instance and sale_order_instance.taobao_trade_status in ['WAIT_SELLER_SEND_GOODS', 'WAIT_BUYER_CONFIRM_GOODS', 'TRADE_FINISHED', 'TRADE_BUYER_SIGNED']:
            sale_order_obj._taobao_reopen_order(pool, cr, uid, [sale_order_instance.id])
            sale_order_obj._taobao_confirm_order(pool, cr, uid, [sale_order_instance.id])

        cr.commit()
    finally:
        cr.close()


@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeClose')
def TaobaoTradeClose(dbname, uid, app_key, rsp):
    #关闭交易
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        sale_order_obj._taobao_cancel_order(pool, cr, uid, sale_order_obj.search(cr, uid, [('origin','=','TB%s' % notify_trade.tid)]))

        cr.commit()
    finally:
        cr.close()


@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeBuyerPay')
def TaobaoTradeBuyerPay(dbname, uid, app_key, rsp):
    #买家付款
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_instance = sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        if sale_order_instance and sale_order_instance.taobao_trade_status in ['WAIT_SELLER_SEND_GOODS', 'WAIT_BUYER_CONFIRM_GOODS', 'TRADE_FINISHED', 'TRADE_BUYER_SIGNED']:
            sale_order_obj._taobao_confirm_order(pool, cr, uid, [sale_order_instance.id])

        cr.commit()
    finally:
        cr.close()

def TaobaoTradeDelayConfirmPay(cr, uid, app_key, rsp):
    #延迟收货
    pass

@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradePartlyRefund')
def TaobaoTradePartlyRefund(dbname, uid, app_key, rsp):
    #子订单退款成功
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_obj._taobao_cancel_order(pool, cr, uid, sale_order_obj.search(cr, uid, [('origin','=','TB%s' % notify_trade.tid)]))
        sale_order_instance = sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        if sale_order_instance and sale_order_instance.taobao_trade_status in ['WAIT_SELLER_SEND_GOODS', 'WAIT_BUYER_CONFIRM_GOODS', 'TRADE_FINISHED', 'TRADE_BUYER_SIGNED']:
            sale_order_obj._taobao_reopen_order(pool, cr, uid, [sale_order_instance.id])
            sale_order_obj._taobao_confirm_order(pool, cr, uid, [sale_order_instance.id])
        cr.commit()
    finally:
        cr.close()

def TaobaoTradePartlyConfirmPay(cr, uid, app_key, rsp):
    #子订单付款成功
    pass

@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeSuccess')
def TaobaoTradeSuccess(dbname, uid, app_key, rsp):
    #买家确认收货
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_instance = sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        if sale_order_instance and sale_order_instance.taobao_trade_status in ['WAIT_SELLER_SEND_GOODS', 'WAIT_BUYER_CONFIRM_GOODS', 'TRADE_FINISHED', 'TRADE_BUYER_SIGNED']:
            sale_order_obj._taobao_confirm_order(pool, cr, uid, [sale_order_instance.id])
            sale_order_obj._taobao_order_ship(pool, cr, uid, [sale_order_instance.id], top)
            sale_order_obj._taobao_create_invoice(pool, cr, uid, [sale_order_instance.id])
            sale_order_obj._taobao_pay_invoice(pool, cr, uid, shop, [sale_order_instance.id])

        cr.commit()

        # 添加评价
        if shop.enable_auto_rate:
            pool.get('taobao.rate')._top_trade_rate_add(top, notify_trade.tid, content = shop.taobao_rate_content)

    finally:
        cr.close()

def TaobaoTradeTimeoutRemind(dbname, uid, app_key, rsp):
    #交易超时提醒
    pass

def TaobaoTradeRated(dbname, uid, app_key, rsp):
    #买家评价交易
    #TODO check bad rated
    pass

@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeMemoModified')
def TaobaoTradeMemoModified(dbname, uid, app_key, rsp):
    #交易备注修改
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        cr.commit()
    finally:
        cr.close()

@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeLogisticsAddressChanged')
def TaobaoTradeLogisticsAddressChanged(dbname, uid, app_key, rsp):
    #修改交易收货地址
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        cr.commit()
    finally:
        cr.close()

@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeChanged')
def TaobaoTradeChanged(dbname, uid, app_key, rsp):
    #修改订单信息（SKU等）
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_instance = sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        if sale_order_instance and sale_order_instance.taobao_trade_status in ['WAIT_SELLER_SEND_GOODS', 'WAIT_BUYER_CONFIRM_GOODS', 'TRADE_FINISHED', 'TRADE_BUYER_SIGNED']:
            sale_order_obj._taobao_confirm_order(pool, cr, uid, [sale_order_instance.id])
        cr.commit()
    finally:
        cr.close()

@mq_client
@msg_route(code = 202, notify = 'notify_trade', status = 'TradeSellerShip')
def TaobaoTradeSellerShip(dbname, uid, app_key, rsp):
    #卖家发货
    notify_trade = rsp.packet.msg.notify_trade
    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()
    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        sale_order_instance = sale_order_obj._taobao_save_fullinfo(pool, cr, uid, notify_trade.tid, shop, top)
        if sale_order_instance and sale_order_instance.taobao_trade_status in ['WAIT_SELLER_SEND_GOODS', 'WAIT_BUYER_CONFIRM_GOODS', 'TRADE_FINISHED', 'TRADE_BUYER_SIGNED']:
            sale_order_obj._taobao_confirm_order(pool, cr, uid, [sale_order_instance.id])
            sale_order_obj._taobao_order_ship(pool, cr, uid, [sale_order_instance.id], top)
            sale_order_obj._taobao_create_invoice(pool, cr, uid, [sale_order_instance.id])
        cr.commit()
    finally:
        cr.close()
    #TODO send sms to client


@mq_client
@msg_route(code = 9999, notify = 'import_taobao_order')
def import_taobao_order(dbname, uid, app_key, rsp):
    trade = rsp.packet.msg.import_taobao_order

    pool = openerp.pooler.get_pool(dbname)
    cr = pool.db.cursor()

    try:
        shop = pool.get('taobao.shop')._get(cr, uid, args = [('taobao_app_key','=',app_key)])
        top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
        sale_order_obj = pool.get('sale.order')
        if not trade.status:
            rsp = sale_order_obj._top_trade_fullinfo_get(top, trade.tid)
            trade['status'] = rsp.status
    finally:
        cr.close()

    job = {}
    if trade.status == 'WAIT_SELLER_SEND_GOODS':
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"notify_trade":{"topic":"trade", "status":"TradeBuyerPay", "tid": trade.tid,}}, "code": 202}}
    elif trade.status == 'WAIT_BUYER_CONFIRM_GOODS':
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"notify_trade":{"topic":"trade", "status":"TradeSellerShip", "tid": trade.tid,}}, "code": 202}}
    elif trade.status == 'WAIT_BUYER_PAY':
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"notify_trade":{"topic":"trade", "status":"TradeAlipayCreate", "tid": trade.tid,}}, "code": 202}}
    elif trade.status == 'TRADE_CLOSED_BY_TAOBAO':
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"notify_trade":{"topic":"trade", "status":"TradeClose", "tid": trade.tid,}}, "code": 202}}
    elif trade.status == 'TRADE_CLOSED':
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"notify_trade":{"topic":"trade", "status":"TradeClose", "tid": trade.tid,}}, "code": 202}}
        #job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"notify_refund":{"topic":"refund", "status":"RefundSuccess", "tid": trade.tid,}}, "code": 202}}
    elif trade.status == 'TRADE_NO_CREATE_PAY':
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"notify_trade":{"topic":"trade", "status":"TradeCreate", "tid": trade.tid,}}, "code": 202}}
    elif trade.status == 'TRADE_FINISHED':
        job = {"taobao_app_key": shop.taobao_app_key, "packet": {"msg": {"notify_trade":{"topic":"trade", "status":"TradeSuccess", "tid": trade.tid,}}, "code": 202}}

    if job:
        from taobao_shop import TaobaoMsgRouter
        TaobaoMsgRouter(dbname, uid, app_key, job)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
