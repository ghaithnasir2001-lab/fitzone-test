from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneClassSchedule(models.Model):
    _name = 'fitzone.class.schedule'
    _description = 'FitZone Class Schedule'

    class_id = fields.Many2one(
        'fitzone.class',
        string='Class',
        required=True
    )

    class_type = fields.Selection(
        related='class_id.class_type',
        string='Class Type',
        store=False
    )

    facility_id = fields.Many2one(
        'fitzone.facility',
        string='Facility',
        required=True
    )

    start_datetime = fields.Datetime(
        string='Start Date & Time',
        required=True
    )

    end_datetime = fields.Datetime(
        string='End Date & Time',
        required=True
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.constrains('start_datetime', 'end_datetime')
    def _check_datetime_range(self):
        for record in self:
            if record.start_datetime >= record.end_datetime:
                raise ValidationError(
                    'End Date & Time must be later than Start Date & Time.'
                )

    @api.constrains(
        'facility_id',
        'start_datetime',
        'end_datetime'
    )
    def _check_facility_schedule_overlap(self):
        for record in self:
            overlapping_schedule = self.search([
                ('id', '!=', record.id),
                ('facility_id', '=', record.facility_id.id),
                ('start_datetime', '<', record.end_datetime),
                ('end_datetime', '>', record.start_datetime),
            ], limit=1)

            if overlapping_schedule:
                raise ValidationError(
                    'A facility cannot have overlapping class schedules.'
                )