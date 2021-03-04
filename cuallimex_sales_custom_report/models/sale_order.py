from odoo import models, fields, api
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    note1 = fields.Text('Notes')
