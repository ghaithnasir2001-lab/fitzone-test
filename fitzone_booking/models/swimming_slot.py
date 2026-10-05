from odoo import fields, models


class FitZoneSwimmingSlot(models.Model):
    _name = 'fitzone.swimming.slot'
    _description = 'FitZone Swimming Slot'

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