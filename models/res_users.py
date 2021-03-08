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

from odoo import fields, models, api, SUPERUSER_ID, _


class res_users(models.Model):
    _inherit = 'res.users'

    kitchen_screen_user = fields.Selection([('cook','Cook'),('manager','Manager')],string="Kitchen Screen User")
    pos_category_ids = fields.Many2many('pos.category', string="POS Categories")
    default_pos = fields.Many2one('pos.config',string="POS Config")
    cook_user_ids = fields.Many2many('res.users','cook_user_rel','user_id','cook_user_id', string='Cook Users')
    
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: