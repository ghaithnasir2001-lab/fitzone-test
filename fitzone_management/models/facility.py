from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneFacility(models.Model):
    _name = 'fitzone.facility'
    _description = 'FitZone Facility'

    name = fields.Char(
        string='Name',
        required=True
    )

    facility_type = fields.Selection(
        [
            ('yoga', 'Yoga'),
            ('pilates', 'Pilates'),
            ('crossfit', 'CrossFit'),
            ('swimming', 'Swimming'),
        ],
        string='Facility Type'
    )

    booking_method = fields.Selection(
        [
            ('direct', 'Direct Booking'),
            ('class_schedule', 'Class Schedule'),
            ('swimming_slot', 'Swimming Slot'),
        ],
        string='Booking Method',
        required=True,
        default='direct'
    )

    capacity = fields.Integer(
        string='Capacity'
    )

    state = fields.Selection(
        [
            ('available', 'Available'),
            ('maintenance', 'Maintenance'),
            ('closed', 'Closed'),
        ],
        string='State',
        default='available'
    )

    description = fields.Text(
        string='Description'
    )

    @api.constrains('capacity')
    def _check_capacity(self):
        for record in self:
            if record.capacity < 0:
                raise ValidationError(
                    'Facility capacity cannot be negative.'
                )