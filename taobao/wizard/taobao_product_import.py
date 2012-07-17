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
import time
from ..taobao_shop import TaobaoMsgRouter

class taobao_product_search(osv.osv_memory):
    _name = "taobao.product.search"
    _description = "Search Taobao Item"
    _columns = {
            'taobao_shop_id': fields.many2one('taobao.shop', 'Taobao Shop', required=True),
            'taobao_search_q': fields.char(u'搜索关键字', size = 256),
            }

    def search_product(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        product_import_lines = []
        for top_search_obj in self.browse(cr, uid, ids, context=context):
            shop = top_search_obj.taobao_shop_id
            context['taobao_shop_id'] = shop.id
            top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)
            items = self.pool.get('taobao.product')._top_items_get(shop, top, top_search_obj.taobao_search_q)
            for item in items:
                product_import_lines.append({
                    'taobao_item_num_iid': item.num_iid,
                    'taobao_item_title': item.title,
                    'taobao_item_pic_url': item.pic_url ,
                    'taobao_item_price': float(item.price),
                    'taobao_item_volume': int(item.volume),
                    })

        context['product_import_lines'] = product_import_lines

        return {
            'name': 'Import Product',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'taobao.product.import',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        record_id = context and context.get('active_id', False) or False
        res = super(taobao_product_search, self).default_get(cr, uid, fields, context=context)

        taobao_shop = self.pool.get('taobao.shop').browse(cr, uid, record_id, context=context)
        if 'taobao_shop_id' in fields and taobao_shop:
            res.update({'taobao_shop_id':taobao_shop.id})
        return res

class taobao_product_import_line(osv.osv_memory):
    _name = "taobao.product.import.line"
    _description = "Taobao Product Import Line"
    _columns = {
            'taobao_item_num_iid': fields.char(u'淘宝产品数字编号', size = 128, required=True),
            'taobao_item_title': fields.char(u'淘宝产品标题', size = 128),
            'taobao_item_pic_url': fields.char(u'图片地址', size = 256),
            'taobao_item_price': fields.float(u'售价'),
            'taobao_item_volume': fields.integer(u'最近成交量'),
            'wizard_id' : fields.many2one('taobao.product.import', string="Wizard"),
            }


class taobao_product_import(osv.osv_memory):
    _name = "taobao.product.import"
    _description = "Import Taobao Product"
    _columns = {
            'taobao_shop_id': fields.many2one('taobao.shop', 'Taobao Shop', required=True),
            'taobao_product_category_id': fields.many2one('product.category', u'淘宝产品分类', select=1, required=True, domain="[('type','=','normal')]"),
            'taobao_product_supplier' : fields.many2one('res.partner', 'Supplier', required=True,domain = [('supplier','=',True)], ondelete='cascade', help="Supplier of this product"),
            'taobao_product_location_id': fields.many2one('stock.location', u'淘宝产品库位', required=True, domain="[('usage', '=', 'internal')]"),

            'taobao_product_warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', required=True, ondelete="cascade"),
            'taobao_product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
            'taobao_product_cost_method': fields.selection([('standard','Standard Price'), ('average','Average Price')], 'Costing Method', required=True,
            help="Standard Price: the cost price is fixed and recomputed periodically (usually at the end of the year), Average Price: the cost price is recomputed at each reception of products."),
            'taobao_product_type': fields.selection([('product','Stockable Product'),('consu', 'Consumable'),('service','Service')], 'Product Type', required=True, help="Will change the way procurements are processed. Consumable are product where you don't manage stock."),
            'taobao_product_supply_method': fields.selection([('produce','Produce'),('buy','Buy')], 'Supply method', required=True, help="Produce will generate production order or tasks, according to the product type. Buy will trigger purchase orders when requested."),
            'taobao_product_procure_method': fields.selection([('make_to_stock','Make to Stock'),('make_to_order','Make to Order')], 'Procurement Method', required=True, help="'Make to Stock': When needed, take from the stock or wait until re-supplying. 'Make to Order': When needed, purchase or produce for the procurement request."),
            'taobao_product_min_qty': fields.float('Min Quantity', required=True,
            help="When the virtual stock goes below the Min Quantity specified for this field, OpenERP generates "\
            "a procurement to bring the virtual stock to the Max Quantity."),
            'taobao_product_max_qty': fields.float('Max Quantity', required=True,
            help="When the virtual stock goes below the Min Quantity, OpenERP generates "\
            "a procurement to bring the virtual stock to the Quantity specified as Max Quantity."),

            'is_update_stock': fields.boolean(u'是否更新库存'),
            'product_import_lines' : fields.one2many('taobao.product.import.line', 'wizard_id', u'淘宝产品列表'),
            }
    _defaults = {
            'is_update_stock': True,
            }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(taobao_product_import, self).default_get(cr, uid, fields, context=context)
        if 'product_import_lines' in fields and context.get('product_import_lines', False):
            res.update({'product_import_lines': context['product_import_lines']})

        taobao_shop = self.pool.get('taobao.shop').browse(cr, uid, context.get('taobao_shop_id', False), context=context)
        if 'taobao_shop_id' in fields and taobao_shop:
            res.update({'taobao_shop_id':taobao_shop.id})

        if 'taobao_product_category_id' in fields and taobao_shop:
            res.update({'taobao_product_category_id': taobao_shop.taobao_product_category_id.id})
        if 'taobao_product_supplier' in fields and taobao_shop:
            res.update({'taobao_product_supplier': taobao_shop.taobao_product_supplier.id})
        if 'taobao_product_location_id' in fields and taobao_shop:
            res.update({'taobao_product_location_id': taobao_shop.taobao_product_location_id.id})
        if 'taobao_product_warehouse_id' in fields and taobao_shop:
            res.update({'taobao_product_warehouse_id': taobao_shop.taobao_product_warehouse_id.id})
        if 'taobao_product_uom' in fields and taobao_shop:
            res.update({'taobao_product_uom': taobao_shop.taobao_product_uom.id})
        if 'taobao_product_cost_method' in fields and taobao_shop:
            res.update({'taobao_product_cost_method': taobao_shop.taobao_product_cost_method})
        if 'taobao_product_type' in fields and taobao_shop:
            res.update({'taobao_product_type': taobao_shop.taobao_product_type})
        if 'taobao_product_supply_method' in fields and taobao_shop:
            res.update({'taobao_product_supply_method': taobao_shop.taobao_product_supply_method})
        if 'taobao_product_procure_method' in fields and taobao_shop:
            res.update({'taobao_product_procure_method': taobao_shop.taobao_product_procure_method})
        if 'taobao_product_min_qty' in fields and taobao_shop:
            res.update({'taobao_product_min_qty': taobao_shop.taobao_product_min_qty})
        if 'taobao_product_max_qty' in fields and taobao_shop:
            res.update({'taobao_product_max_qty': taobao_shop.taobao_product_max_qty})

        return res

    def import_product(self, cr, uid, ids, context=None):
        for product_import_obj in self.browse(cr, uid, ids, context=context):

            shop = product_import_obj.taobao_shop_id
            top = TOP(shop.taobao_app_key, shop.taobao_app_secret, shop.taobao_session_key)

            for line in product_import_obj.product_import_lines:
                job = {"taobao_app_key": top.app_key, "packet": {"msg": {
                    "import_taobao_product":{
                        "taobao_num_iid": line.taobao_item_num_iid,
                        "taobao_product_category_id": product_import_obj.taobao_product_category_id.id,
                        "taobao_product_supplier": product_import_obj.taobao_product_supplier.id,
                        "taobao_product_warehouse_id": product_import_obj.taobao_product_warehouse_id.id,
                        "taobao_product_location_id": product_import_obj.taobao_product_location_id.id,
                        "taobao_product_cost_method": product_import_obj.taobao_product_cost_method,
                        "taobao_product_type": product_import_obj.taobao_product_type,
                        "taobao_product_supply_method": product_import_obj.taobao_product_supply_method,
                        "taobao_product_procure_method": product_import_obj.taobao_product_procure_method,
                        "taobao_product_min_qty": product_import_obj.taobao_product_min_qty,
                        "taobao_product_max_qty": product_import_obj.taobao_product_max_qty,
                        "taobao_product_uom": product_import_obj.taobao_product_uom.id,
                        "is_update_stock": product_import_obj.is_update_stock,
                        }
                    }, "code": 9999}}
                TaobaoMsgRouter(cr.dbname, uid, shop.taobao_app_key, job)

        return {
                'type': 'ir.actions.act_window_close',
                }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
