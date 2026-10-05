from odoo import fields, models


class FitZoneClassSchedule(models.Model):
    _name = 'fitzone.class.schedule'
    _description = 'FitZone Class Schedule'

    class_id = fields.Many2one(
        'fitzone.class',
        string='Class',
        required=True
    )

    appointment_id = fields.Many2one(
        'fitzone.appointment',
        string='Appointment',
        required=True
    )

    _sql_constraints = [
        (
            'appointment_unique',
            'unique(appointment_id)',
            'Each appointment can be linked to only one class schedule.'
        ),
    ]