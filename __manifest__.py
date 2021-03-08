# -*- coding: utf-8 -*-
#################################################################################
# Author      : Acespritech Solutions Pvt. Ltd. (<www.acespritech.com>)
# Copyright(c): 2012-Present Acespritech Solutions Pvt. Ltd.
# All Rights Reserved.
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################

{
    'name': 'POS Kitchen screen',
    'version': '1.0',
    'category': 'Point of Sale',
    'website': 'http://www.acespritech.com',
    'price': 30.0,
    'currency': 'EUR',
    'summary': "A Screen for kitchen staff.",
    'description': "POS kitchen Screen shows orders and their state to Cook and Manager",
    'author': "Acespritech Solutions Pvt. Ltd.",
    'website': "www.acespritech.com",
    'depends': ['point_of_sale','bus','pos_restaurant'],
    'data': [
        'views/res_users_view.xml',
        'views/pos_kitchen_screen.xml',
        'views/kitchen_screen_view.xml',
        'security/ir.model.access.csv',
    ],
    'qweb': ['static/src/xml/pos.xml'],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
