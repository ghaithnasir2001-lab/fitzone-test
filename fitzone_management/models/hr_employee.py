from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    fitzone_registration_number = fields.Char(
        string='Official Employee Number',
        copy=False,
    )

    fitzone_staff_type = fields.Selection(
        [
            ('trainer', 'Trainer'),
            ('nurse', 'Nurse'),
            ('physiotherapist', 'Physiotherapist'),
            ('nutritionist', 'Nutritionist'),
            ('receptionist', 'Receptionist'),
            ('sales', 'Sales'),
            ('management', 'Management'),
        ],
        string='Staff Type',
    )

    fitzone_specialty = fields.Char(
        string='Specialty',
    )
