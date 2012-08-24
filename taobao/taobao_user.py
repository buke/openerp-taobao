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

from osv import fields,osv
from taobao_base import TaobaoMixin

class taobao_shop(osv.osv, TaobaoMixin):
    _inherit = "taobao.shop"
    _columns = {
            # taobao user
            'taobao_user_category_id': fields.many2one('res.partner.category', u'淘宝用户分类', select=1, required=True),
            }

    _defaults = {
            }



class res_partner_bank(osv.osv, TaobaoMixin):
    _inherit = "res.partner.bank"

class res_partner_address(osv.osv, TaobaoMixin):
    _inherit = 'res.partner.address'
    _columns = {
            'taobao_full_address': fields.char(u'淘宝地址', size=512),
            }


class res_partner(osv.osv, TaobaoMixin):
    _inherit = 'res.partner'

    def _get_taobao_user_profile(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for user in self.browse(cr, uid, ids, context=context):
            res[user.id] = 'http://rate.taobao.com/rate.htm?user_id=%s' % user.taobao_user_id
        return res

    _columns = {
            'state': fields.related('address', 'state_id', type='many2one', relation='res.country.state', string=u'省份'),
            'taobao_user_id': fields.char(u'用户数字ID', size=64),
            'taobao_nick': fields.char(u'淘宝用户名', size=64),
            'taobao_user_profile': fields.function(_get_taobao_user_profile, type='char', string=u'淘宝用户信息'),
            'taobao_receive_sms_remind': fields.boolean(u'接收短信提醒'),
            'taobao_receive_email_remind': fields.boolean(u'接收邮件提醒'),
            }

    #_sql_constraints = [('taobao_user_id_uniq','unique(taobao_user_id)', 'Taobao User must be unique!')]
    _sql_constraints = [('taobao_nick_uniq','unique(taobao_nick)', 'Taobao Nick must be unique!')]

    _defaults = {
            'taobao_receive_sms_remind': True,
            'taobao_receive_email_remind': True,
            }


    def _top_user_get(self, top, nick=None):
        fields = [
                'user_id','uid','nick','sex', 'buyer_credit', 'seller_credit', 'zip', 'city',
                'state', 'country', 'district', 'area', 'created', 'last_visit', 'birthday',
                'type', 'has_more_pic', 'item_img_num', 'item_img_size', 'prop_img_num',
                'prop_img_size', 'auto_repost', 'promoted_type', 'status', 'alipay_bind',
                'consumer_protection', 'alipay_account', 'alipay_no', 'avatar', 'liangpin',
                'sign_food_seller_promise', 'has_shop', 'is_lightning_consignment', 'has_sub_stock'
                'is_golden_seller', 'vip_info', 'email', 'magazine_subscribe', 'vertical_market',
                'online_gaming',
                ]
        if nick:
            rsp =top('taobao.user.get', nick=nick, fields=fields)
        else:
            rsp =top('taobao.user.get', fields=fields)

        if rsp and rsp.has_key('user'):
            top_user = rsp.user
            if top_user.has_key('buyer_credit'):
                top_user['buyer_credit_level'] = top_user.buyer_credit.level
                top_user['buyer_credit_score'] = top_user.buyer_credit.score
                top_user['buyer_credit_total_num'] = top_user.buyer_credit.total_num
                top_user['buyer_credit_good_num'] = top_user.buyer_credit.good_num
            if top_user.has_key('seller_credit'):
                top_user['seller_credit_level'] = top_user.seller_credit.level
                top_user['seller_credit_score'] = top_user.seller_credit.score
                top_user['seller_credit_total_num'] = top_user.seller_credit.total_num
                top_user['seller_credit_good_num'] = top_user.seller_credit.good_num
            return top_user
        else:
            return None




    # vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
