openerp-taobao
==============

Taobao OpenERP Connector

作者： wangbuke@gmail.com

Update:
----------
2012-12-03 淘宝API变化taobao.user.get 变为增值接口, 普通卖家无法使用

2012-11-26 淘宝API变化taobao.items.get 不能使用，换为 taobao.items.onsale.get

2012-08-24 淘宝API变化，不能获取user_id

功能:
------


1. 接受淘宝主动通知，自动添加、确认订单、发货等。


2. 同步淘宝订单


3. 导入淘宝产品, 同步库存


4. 导入淘宝用户


5. 自动评价，中差评预警


6. 跟踪淘宝订单物流信息, 签收提醒


7. .... 等等等 (懒的写了，自己发现吧)


系统要求：
------


OpenERP 6.1

beanstalkd

pycurl


安装说明等请查看 http://my.oschina.net/wangbuke/blog/67771  

