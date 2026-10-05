from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    fitzone_registration_number = fields.Char(
        string='Employee Number',
        copy=False,
    )

    fitzone_specialty = fields.Char(
        string='Specialty',
    )
