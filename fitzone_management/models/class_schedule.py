from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneClassSchedule(models.Model):
    _name = 'fitzone.class.schedule'
    _description = 'FitZone Class Schedule'
    _rec_name = 'name'

    name = fields.Char(
        string='Schedule',
        compute='_compute_name',
        store=True
    )

    class_id = fields.Many2one(
        'fitzone.class',
        string='Class',
        required=True
    )
    trainer_id = fields.Many2one(
        'fitzone.trainer',
        string='Trainer',
        required=True,
        ondelete='restrict'
    )

    class_type = fields.Selection(
        related='class_id.class_type',
        string='Class Type',
        store=False
    )

    facility_id = fields.Many2one(
        'fitzone.facility',
        string='Facility',
        required=True,
        domain=[
            ('booking_method', '=', 'class_schedule'),
            ('state', '=', 'available')
        ]
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

    @api.depends(
        'class_id',
        'facility_id',
        'start_datetime',
        'end_datetime'
    )
    def _compute_name(self):
        for record in self:
            if not record.class_id or not record.start_datetime:
                record.name = 'New Schedule'
                continue

            start = fields.Datetime.context_timestamp(
                record,
                record.start_datetime
            )

            end = (
                fields.Datetime.context_timestamp(
                    record,
                    record.end_datetime
                )
                if record.end_datetime
                else None
            )

            date = start.strftime('%d/%m/%Y')
            start_time = start.strftime('%I:%M %p').lstrip('0')

            if end:
                end_time = end.strftime('%I:%M %p').lstrip('0')
                time_range = f'{start_time}–{end_time}'
            else:
                time_range = start_time

            facility_name = (
                record.facility_id.name
                if record.facility_id
                else ''
            )

            parts = [
                record.class_id.name,
                date,
                time_range,
                facility_name
            ]

            record.name = ' — '.join(
                part for part in parts if part
            )

    @api.constrains('facility_id')
    def _check_facility_availability(self):
        for record in self:
            if record.facility_id.booking_method != 'class_schedule':
                raise ValidationError(
                    'A class schedule can only use a facility with Class Schedule booking.'
                )

            if record.facility_id.state != 'available':
                raise ValidationError(
                    'A class schedule can only use an available facility.'
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