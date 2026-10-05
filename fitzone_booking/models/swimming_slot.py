from odoo import fields, models


class FitZoneSwimmingSlot(models.Model):
    _name = 'fitzone.swimming.slot'
    _description = 'FitZone Swimming Slot'

    appointment_id = fields.Many2one(
        'fitzone.appointment',
        string='Appointment',
        required=True
    )

    name = fields.Char(
        string='Name',
        required=True
    )

    slot_type = fields.Selection(
        [
            ('free', 'Free'),
            ('group', 'Group'),
            ('private', 'Private'),
        ],
        string='Slot Type',
        required=True
    )

    price = fields.Float(
        string='Price'
    )

    created_by = fields.Many2one(
        'hr.employee',
        string='Created By'
    )

    _sql_constraints = [
        (
            'appointment_unique',
            'unique(appointment_id)',
            'Each appointment can be linked to only one swimming slot.'
        ),
    ]