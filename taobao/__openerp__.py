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

{
    "name": "Taobao OpenERP Connector",
    "author" : "wangbuke@gmail.com",
    'website': 'http://my.oschina.net/wangbuke',
    'category': 'Sales Management',
    "depends" : [
        'base',
        'product',
        'account',
        'account_voucher',
        'sale',
        'stock',
        'delivery',
        'crm_helpdesk',
        ],
    "init_xml" : [
    ],
    "demo_xml" : [],
    'update_xml': [
           'security/ir.model.access.csv',
           'data/res.country.state.csv',
           'data/bank_data.xml',
           'data/delivery_data.xml',
           'taobao_shop_view.xml',
           'wizard/taobao_product_import.xml',
           'wizard/taobao_order_import.xml',
           'wizard/taobao_stock_update.xml',
           'wizard/taobao_picking_update.xml',
           'taobao_product_view.xml',
           'taobao_packet_view.xml',
           'taobao_order_view.xml',
           'taobao_user_view.xml',
           'taobao_rate_view.xml',
           'taobao_refund_view.xml',
           'taobao_delivery_tracking_view.xml',
    ],
    "description":
        """
        Taobao Connect Module

        系统要求：
            beanstalkd (windows 用户请搜索 cgywin beanstalkd)

        功能:
        1. 接受淘宝主动通知，自动添加、确认订单、发货等。
        2. 同步淘宝订单
        3. 导入淘宝产品, 同步库存
        4. 导入淘宝用户
        5. 自动评价，中差评预警
        6. 跟踪淘宝订单物流信息, 签收提醒
        7. .... 等等等 (懒的写了，自己发现吧)

        wangbuke@gmail.com

        """,
    "version": "0.1",
    'installable': True,
    'auto_install': False,
    "js": [],
    "css": [],
    'images': [],
}
