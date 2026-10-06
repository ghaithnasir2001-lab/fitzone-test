from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneSwimmingSlot(models.Model):
    _name = 'fitzone.swimming.slot'
    _description = 'FitZone Swimming Slot'

    name = fields.Char(
        string='Name',
        required=True
    )

    start_time = fields.Float(
        string='Start Time',
        required=True
    )

    end_time = fields.Float(
        string='End Time',
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

    @api.constrains('price')
    def _check_price(self):
        for record in self:
            if record.price < 0:
                raise ValidationError(
                    'Swimming slot price cannot be negative.'
                )

    @api.constrains('start_time', 'end_time')
    def _check_time_range(self):
        for record in self:
            if record.start_time >= record.end_time:
                raise ValidationError(
                    'Start Time must be earlier than End Time.'
                )