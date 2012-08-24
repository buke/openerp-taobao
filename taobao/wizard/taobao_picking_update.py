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
from ..taobao_top import TOP

class taobao_picking_update_line(osv.osv_memory):
    _name = "taobao.picking.update.line"
    _description = "Taobao Picking Stock Update Line"
    _columns = {
            'taobao_product_id': fields.many2one('taobao.product', 'Taobao Product'),
            'product_product_id': fields.many2one('product.product', 'Product'),
            'qty': fields.float(u'数量', required=True),
            'taobao_num_iid': fields.char(u'商品数字编码', size = 64),
            'taobao_sku_id': fields.char(u'Sku id', size = 64),
            'taobao_shop_id': fields.many2one('taobao.shop', 'Taobao Shop'),
            'update_type': fields.selection([
                (1, u'全量更新'),
                (2, u'增量更新'),
                ],
                u'库存更新方式',
                ),
            'wizard_id' : fields.many2one('taobao.picking.update', string="Wizard"),
            }

    _defaults = {
            'update_type': 1,
            }



class taobao_picking_update(osv.osv_memory):
    _name = "taobao.picking.update"
    _description = "Taobao Picking Update"

    _columns = {
            'stock_update_lines' : fields.one2many('taobao.picking.update.line', 'wizard_id', u'产品列表'),
            }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(taobao_picking_update, self).default_get(cr, uid, fields, context=context)

        active_model = context.get('active_model', False)
        active_ids = context.get('active_ids', False)

        stock_update_lines = []
        if active_model == 'stock.picking' and active_ids:
            for picking in self.pool.get('stock.picking').browse(cr, uid, active_ids, context=context):
                for move in picking.move_lines:
                    qty = move.product_qty
                    for taobao_product in move.product_id.taobao_product_ids:
                        stock_update_lines.append({
                            'taobao_product_id' : taobao_product.id,
                            'product_product_id' : move.product_id.id,
                            'qty' : qty,
                            'taobao_num_iid': taobao_product.taobao_num_iid,
                            'taobao_sku_id': taobao_product.taobao_sku_id,
                            'taobao_shop_id': taobao_product.taobao_shop_id.id,
                            'update_type': 2,
                        })

        context['stock_update_lines'] = stock_update_lines

        if 'stock_update_lines' in fields and context.has_key('stock_update_lines'):
            res.update({'stock_update_lines': context['stock_update_lines']})

        return res

    def update_stock(self, cr, uid, ids, context=None):
        for stock_update_obj in self.browse(cr, uid, ids, context=context):
            for line in stock_update_obj.stock_update_lines:
                shop = line.taobao_shop_id
                top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
                self.pool.get('taobao.product')._top_item_quantity_update(top, line.qty, line.taobao_num_iid, sku_id = line.taobao_sku_id, update_type = line.update_type)

        return {'type': 'ir.actions.act_window_close'}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
