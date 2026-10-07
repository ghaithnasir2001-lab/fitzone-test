from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneSwimmingSlot(models.Model):
    _name = 'fitzone.swimming.slot'
    _description = 'FitZone Swimming Slot'
    _rec_name = 'name'

    name = fields.Char(
        string='Slot',
        compute='_compute_name',
        store=True
    )

    facility_id = fields.Many2one(
        'fitzone.facility',
        string='Facility',
        required=True,
        domain=[('facility_type', '=', 'swimming')]
    )

    start_datetime = fields.Datetime(
        string='Start Date & Time',
        required=True
    )

    end_datetime = fields.Datetime(
        string='End Date & Time',
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

    @api.depends(
        'slot_type',
        'start_datetime',
        'end_datetime'
    )
    def _compute_name(self):
        for record in self:
            if not record.slot_type or not record.start_datetime:
                record.name = 'New Swimming Slot'
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

            slot_type = dict(
                record._fields['slot_type'].selection
            ).get(record.slot_type, record.slot_type)

            start_time = start.strftime(
                '%I:%M %p'
            ).lstrip('0')

            if end:
                end_time = end.strftime(
                    '%I:%M %p'
                ).lstrip('0')

                time_range = (
                    f'{start_time}–{end_time}'
                )
            else:
                time_range = start_time

            record.name = (
                f'{slot_type} — {time_range}'
            )

    @api.constrains('price')
    def _check_price(self):
        for record in self:
            if record.price < 0:
                raise ValidationError(
                    'Swimming slot price cannot be negative.'
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
    def _check_slot_overlap(self):
        for record in self:
            overlapping_slot = self.search([
                ('id', '!=', record.id),
                ('facility_id', '=', record.facility_id.id),
                ('start_datetime', '<', record.end_datetime),
                ('end_datetime', '>', record.start_datetime),
            ], limit=1)

            if overlapping_slot:
                raise ValidationError(
                    'This swimming slot overlaps with an existing slot in the same facility.'
                )
