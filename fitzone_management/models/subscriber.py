from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_fitzone_subscriber = fields.Boolean(
        string='FitZone Subscriber',
        default=False
    )

    subscriber_notes = fields.Text(
        string='Subscriber Notes'
    )