from odoo import fields, models


class FitZoneFacility(models.Model):
    _name = 'fitzone.facility'
    _description = 'FitZone Facility'

    name = fields.Char(
        string='Name',
        required=True
    )

    facility_type = fields.Char(
        string='Facility Type'
    )

    capacity = fields.Integer(
        string='Capacity'
    )

    state = fields.Char(
        string='State'
    )

    description = fields.Text(
        string='Description'
    )