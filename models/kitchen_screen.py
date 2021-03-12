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

import logging
import psycopg2
import time
from odoo.tools import float_is_zero
from odoo import models, fields, api, tools, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz
from datetime import datetime
from operator import itemgetter
from timeit import itertools
from itertools import groupby

_logger = logging.getLogger(__name__)




class Pantallas(models.Model):
    _name = 'aspl_pos_kitchen_screen.pantallas'
    _description = 'Pantallas Restaurant'

    name = fields.Char(string='Name')


class PantallasCategoriasPos(models.Model):
    _name = 'aspl_pos_kitchen_screen.pantallas_categorias'
    _description = 'Categorías por pantallaRestaurant'

    pos_category_ids = fields.Many2many('pos.category', relation="pantalla_categorias_rel",string="POS Categories")
    pantalla_id = fields.Many2one('aspl_pos_kitchen_screen.pantallas', string='Pantallas')



class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def load_order_details(self, order_id):
        order_obj = self.browse(int(order_id))
        lines = []
        if order_obj:
            for each in order_obj.lines:
                line = self.load_order_line_details(each.id)
                if line:
                    lines.append(line[0])
        return lines

    @api.model
    def load_order_line_details(self, line_id):
        data = {}
        line_obj = self.env['pos.order.line'].search_read([('id','=',line_id)])
        if line_obj:
            order_obj = self.browse(line_obj[0].get('order_id')[0])
            data['id'] = line_obj[0].get('id')
            data['product_id'] = line_obj[0].get('product_id')
            data['uom_id'] = self.env['product.product'].browse(line_obj[0].get('product_id')[0]).uom_id.name
            data['company_id'] = line_obj[0].get('company_id')
            data['qty'] = line_obj[0].get('qty')
            data['order_line_note'] = line_obj[0].get('order_line_note')
            data['order_id'] = line_obj[0].get('order_id')
            data['state'] = line_obj[0].get('state')
            data['pos_reference'] = order_obj.pos_reference
            data['tabel_id'] = [order_obj.table_id.id, order_obj.table_id.name] if order_obj.table_id else False
            data['floor_id'] = order_obj.table_id.floor_id.name if order_obj.table_id and order_obj.table_id.floor_id else False
        return [data]

    def _order_fields(self,ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        res.update({
            'note': ui_order.get('order_note') or False
        })
        return res

    @api.model
    def create_from_ui(self, orders):
        submitted_references = [o['data']['name'] for o in orders]
        pos_order = self.search([('pos_reference', 'in', submitted_references)])
        existing_orders = pos_order.read(['pos_reference'])
        existing_references = set([o['pos_reference'] for o in existing_orders])
        orders_to_save = [o for o in orders if o['data']['name'] not in existing_references]
        order_ids = []

        order_to_update = [o for o in orders if o['data']['name'] in existing_references]
        # Keep only new orders
        for tmp_order in orders_to_save:
            to_invoice = tmp_order['to_invoice']
            order = tmp_order['data']
            if to_invoice:
                self._match_payment_to_invoice(order)
            pos_order = self._process_order(order)
            order_ids.append(pos_order.id)

            try:
                pos_order.action_pos_order_paid()
            except psycopg2.OperationalError:
                # do not hide transactional errors, the order(s) won't be saved!
                raise
            except Exception as e:
                _logger.error('Could not fully process the POS Order: %s', tools.ustr(e))

            if to_invoice:
                pos_order.action_pos_order_invoice()
                pos_order.invoice_id.sudo().action_invoice_open()
                pos_order.account_move = pos_order.invoice_id.move_id

        # Update draft orders
        for tmp_order in order_to_update:
            for order in pos_order:
                if order.pos_reference == tmp_order['data']['name']:
                    pos_line_ids = self.env['pos.order.line'].search([('order_id', '=', order.id)])
                    if pos_line_ids:
                        pos_cids = []
                        new_cids = []
                        for line_id in pos_line_ids:
                            pos_cids.append(line_id.pos_cid)
                            for line in tmp_order['data']['lines']:
                                if line_id.pos_cid == line[2].get('pos_cid'):
                                    new_cids.append(line[2].get('pos_cid'))
                                    order.write({'lines': [(1, line_id.id, line[2])]})

                        for line in tmp_order['data']['lines']:
                            if line[2].get('pos_cid') not in pos_cids:
                                order.write({'lines': [(0, 0, line[2])]})
                                pos_cids.append(line[2].get('pos_cid'))
                                new_cids.append(line[2].get('pos_cid'))

                        newList = []
                        for item in pos_cids:
                            if item not in new_cids:
                                newList.append(item)

                        order_line_ids = self.env['pos.order.line'].search([('pos_cid', 'in', newList)])
                        if order_line_ids:
                            for each_line in order_line_ids:
                                each_line.unlink()

                    to_invoice = tmp_order['to_invoice']
                    order = tmp_order['data']
                    if to_invoice:
                        self._match_payment_to_invoice(order)
                    pos_order = self._process_order(order)
                    order_ids.append(pos_order.id)

                    try:
                        pos_order.action_pos_order_paid()
                    except psycopg2.OperationalError:
                        # do not hide transactional errors, the order(s) won't be saved!
                        raise
                    except Exception as e:
                        _logger.error('Could not fully process the POS Order: %s', tools.ustr(e))

                    if to_invoice:
                        pos_order.action_pos_order_invoice()
                        pos_order.invoice_id.sudo().action_invoice_open()
                        pos_order.account_move = pos_order.invoice_id.move_id
        self.broadcast_order_data(True)

        return order_ids

    @api.model
    def _process_order(self, order):
        submitted_references = order['name']
        draft_order_id = self.search([('pos_reference', '=', submitted_references)]).id

        if draft_order_id:
            order_id = draft_order_id
            order_obj = self.browse(order_id)
            temp = order.copy()
            temp.pop('statement_ids', None)
            temp.pop('name', None)
            temp.pop('lines',None)
            order_obj.write(temp)
            for payments in order['statement_ids']:
                order_obj.add_payment(self._payment_fields(payments[2]))

            session = self.env['pos.session'].browse(order['pos_session_id'])
            if session.sequence_number <= order['sequence_number']:
                session.write({'sequence_number': order['sequence_number'] + 1})
                session.refresh()

            if not float_is_zero(order['amount_return'], self.env['decimal.precision'].precision_get('Account')):
                cash_journal = session.cash_journal_id
                if not cash_journal:
                    cash_journal_ids = session.statement_ids.filtered(lambda st: st.journal_id.type == 'cash')
                    if not len(cash_journal_ids):
                        raise Warning(_('error!'),
                                      _("No cash statement found for this session. Unable to record returned cash."))
                    cash_journal = cash_journal_ids[0].journal_id
                order_obj.add_payment({
                    'amount': -order['amount_return'],
                    'payment_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'payment_name': _('return'),
                    'journal': cash_journal.id,
                })
            return order_obj

        if not draft_order_id:
            order_id = super(PosOrder, self)._process_order(order)
            return order_id

    @api.model
    def broadcast_order_data(self, new_order):
        notifications = []
        vals = {}
        pos_order = self.search([('lines.state', 'not in', ['cancel', 'done']),
                                 ('amount_total', '>', 0.00)])
        manager_ids = self.env['res.users'].search([('kitchen_screen_user', '=', 'manager')])
        screen_table_data = []
        for order in pos_order:
            order_line_list = []
            for line in order.lines:
                order_line = {
                    'id': line.id,
                    'name': line.product_id.display_name,
                    'qty': line.qty,
                    'table': line.order_id.table_id.name,
                    'floor': line.order_id.table_id.floor_id.name,
                    'time': self.get_session_date(line),
                    'state': line.state,
                    'note': line.order_line_note,
                    'categ_id': line.product_id.product_tmpl_id.pos_categ_id.id,
                    'order': line.order_id.id,
                    'pos_cid': line.pos_cid,
                    'user': line.create_uid.id,
                    'route_id': line.product_id.product_tmpl_id.route_ids.active,
                }
                order_line_list.append(order_line)
            order_dict = {
                'order_id': order.id,
                'order_name': order.name,
                'order_time': self.get_order_date(order),
                'table': order.table_id.name,
                'floor': order.table_id.floor_id.name,
                'customer': order.partner_id.name,
                'order_lines': order_line_list,
                'total': order.amount_total,
                'note': order.note,
                'user_id': order.user_id.id,
            }
            screen_table_data.append(order_dict)
        kitchen_group_data = {}

        sort_group = sorted(screen_table_data, key=itemgetter('user_id'))
        for key, value in itertools.groupby(sort_group, key=itemgetter('user_id')):
            if key not in kitchen_group_data:
                kitchen_group_data.update({key: [x for x in value]})
            else:
                kitchen_group_data[key] = [x for x in value]
                
        if kitchen_group_data:
            for user_id in kitchen_group_data:
                user = self.env['res.users'].browse(user_id)
                if user and user.cook_user_ids:
                    for cook_user_id in user.cook_user_ids:
                        if 'orders' not in vals:
                            vals['orders'] = []
                        for itm in kitchen_group_data[user_id]:
                            if itm not in vals['orders']:
                                vals['orders'].append(itm)

                        if new_order:
                            vals['new_order'] = new_order
                        notifications.append(
                            ((self._cr.dbname, 'pos.order.line', cook_user_id.id), {'screen_display_data': vals}))
                if user and user.kitchen_screen_user != 'cook':
                    if manager_ids:
                        for each_manager in manager_ids:
                            notifications.append(
                                ((self._cr.dbname, 'pos.order.line', each_manager.id), {'screen_display_data': vals}))
        else:
            if manager_ids:
                for each_manager in manager_ids:
                    notifications.append(
                        ((self._cr.dbname, 'pos.order.line', each_manager.id), {'screen_display_data': vals}))
            cook_user_ids = self.env['res.users'].search([('kitchen_screen_user', '=', 'cook')])
            if cook_user_ids:
                for each_cook_id in cook_user_ids:
                    notifications.append(
                        ((self._cr.dbname, 'pos.order.line', each_cook_id.id), {'screen_display_data': vals}))
        if notifications:
            self.env['bus.bus'].sendmany(notifications)
        return True

    @api.multi
    def get_session_date(self, line):
        SQL = """SELECT create_date AT TIME ZONE 'GMT' as create_date  from pos_order_line where id = %d
                   """ % (line.id)
        self._cr.execute(SQL)
        data = self._cr.dictfetchall()
        time = data[0]['create_date']
        return str(time.hour)+ ':' + str(time.minute) + ':' + str(time.second)

    @api.multi
    def get_order_date(self, order):
        SQL = """SELECT date_order AT TIME ZONE 'GMT' as date_order  from pos_order where id = %d
                       """ % (order.id)
        self._cr.execute(SQL)
        data = self._cr.dictfetchall()
        time = data[0]['date_order']
        return str(time.hour) + ':' + str(time.minute) + ':' + str(time.second)

class PosOrderLines(models.Model):
    _inherit = "pos.order.line"

    @api.model
    def update_orderline_state(self,vals):
        order_line = self.browse(vals['order_line_id'])
        res = order_line.sudo().write({
            'state': vals['state']
        });
        vals['pos_reference'] = order_line.order_id.pos_reference
        vals['pos_cid'] = order_line.pos_cid
        notifications = []
        notifications.append(((self._cr.dbname, 'pos.order.line', order_line.create_uid.id), {'order_line_state': vals}))
        self.env['bus.bus'].sendmany(notifications)
        return res

    @api.model
    def update_all_orderline_state(self, vals):
        notifications = []
        if vals:
            for val in vals:
                state = False
                if val.get('route'):
                    if val.get('state') == 'waiting':
                        state = 'done'
                    # elif val.get('state') == 'preparing':
                    #     state = 'delivering'
                    # elif val.get('state') == 'delivering':
                    #     state = 'done'
                    elif val.get('state') == 'cancel':
                        state = 'cancel'
                else:
                    if val.get('state') == 'waiting':
                        state = 'done'
                    # elif val.get('state') == 'delivering':
                    #     state = 'done'
                    elif val.get('state') == 'cancel':
                        state = 'cancel'
                if state:
                    order_line = self.browse(val['order_line_id'])
                    res = order_line.sudo().write({
                        'state': state
                    });
                    val['pos_reference'] = order_line.order_id.pos_reference
                    val['pos_cid'] = order_line.pos_cid
                    val['state'] = state
                    notifications.append(
                        [(self._cr.dbname, 'pos.order.line', order_line.create_uid.id), {'order_line_state': val}])
            if len(notifications) > 0:
                self.env['bus.bus'].sendmany(notifications)
        return True

    # state = fields.Selection(selection=[("waiting", "Waiting"), ("preparing", "Preparing"), ("delivering", "Waiting/deliver"),("done","Done"),("cancel","Cancel")],default="waiting")
    state = fields.Selection(selection=[("waiting", "Waiting"), ("done","Done"),("cancel","Cancel")],default="waiting")
    state_method = fields.Selection(selection=[("waiting", "Waiting"), ("done","Done"),("cancel","Cancel")],default="waiting")
    order_line_note = fields.Text("Order Line Notes")
    pos_cid = fields.Char("pos cid")


class PosConfig(models.Model):
    _inherit = 'pos.config'

    send_to_kitchen = fields.Boolean(string="Send To Kitchen", default=True)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: