from odoo import fields, models


class FitZoneClass(models.Model):
    _name = 'fitzone.class'
    _description = 'FitZone Class'

    service_id = fields.Many2one(
        'product.template',
        string='Service',
        required=True
    )

    name = fields.Char(
        string='Name',
        required=True
    )

    class_type = fields.Char(
        string='Class Type',
        required=True
    )

    description = fields.Text(
        string='Description'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )