from odoo import fields, models


class FitZoneClassSchedule(models.Model):
    _name = 'fitzone.class.schedule'
    _description = 'FitZone Class Schedule'

    class_id = fields.Many2one(
        'fitzone.class',
        string='Class',
        required=True
    )