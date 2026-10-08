from odoo import fields, models


class FitZoneInjuryCause(models.Model):
    _name = 'fitzone.injury.cause'
    _description = 'FitZone Injury Cause'
    _order = 'name'

    name = fields.Char(
        string='Cause',
        required=True,
    )

    description = fields.Text(
        string='Description',
    )

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        'Injury cause name must be unique.',
    )
