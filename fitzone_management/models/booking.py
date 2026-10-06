from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneBooking(models.Model):
    _name = 'fitzone.booking'
    _description = 'FitZone Booking'

    name = fields.Char(
        string='Booking Reference',
        required=True,
        default='New',
        copy=False
    )

    booking_type = fields.Selection(
        [
            ('class', 'Class'),
            ('facility', 'Facility'),
        ],
        string='Booking Type',
        required=True
    )

    class_id = fields.Many2one(
        'fitzone.class',
        string='Class'
    )

    facility_id = fields.Many2one(
        'fitzone.facility',
        string='Facility'
    )

    class_schedule_id = fields.Many2one(
        'fitzone.class.schedule',
        string='Class Schedule'
    )

    swimming_slot_id = fields.Many2one(
        'fitzone.swimming.slot',
        string='Swimming Slot'
    )

    booking_datetime = fields.Datetime(
        string='Booking Date & Time',
        required=True
    )

    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True
    )

    @api.constrains(
        'booking_type',
        'class_id',
        'facility_id',
        'class_schedule_id',
        'swimming_slot_id',
        'booking_datetime'
    )
    def _check_booking_details(self):
        for record in self:

            if record.booking_type == 'class':
                if not record.class_id or not record.class_schedule_id:
                    raise ValidationError(
                        'Class bookings must have a class and a class schedule.'
                    )

                if record.facility_id:
                    raise ValidationError(
                        'Class bookings cannot have a facility.'
                    )

                if record.swimming_slot_id:
                    raise ValidationError(
                        'Class bookings cannot have a swimming slot.'
                    )

                if record.class_schedule_id.class_id != record.class_id:
                    raise ValidationError(
                        'The selected class schedule must belong to the selected class.'
                    )

                if (
                    record.booking_datetime
                    and (
                        record.booking_datetime < record.class_schedule_id.start_datetime
                        or record.booking_datetime >= record.class_schedule_id.end_datetime
                    )
                ):
                    raise ValidationError(
                        'The booking date and time must be within the selected class schedule.'
                    )

            elif record.booking_type == 'facility':
                if not record.facility_id:
                    raise ValidationError(
                        'Facility bookings must have a facility.'
                    )

                if record.class_id or record.class_schedule_id:
                    raise ValidationError(
                        'Facility bookings cannot have a class or class schedule.'
                    )

                if record.facility_id.facility_type == 'swimming':
                    if not record.swimming_slot_id:
                        raise ValidationError(
                            'Swimming bookings must have a swimming slot.'
                        )

                    if record.swimming_slot_id.facility_id != record.facility_id:
                        raise ValidationError(
                            'The selected swimming slot must belong to the selected facility.'
                        )

                    if (
                        record.booking_datetime < record.swimming_slot_id.start_datetime
                        or record.booking_datetime >= record.swimming_slot_id.end_datetime
                    ):
                        raise ValidationError(
                            'The booking date and time must be within the selected swimming slot.'
                        )

                elif record.swimming_slot_id:
                    raise ValidationError(
                        'Swimming slot can only be used for swimming facilities.'
                    )

    @api.constrains(
        'booking_type',
        'class_schedule_id',
        'facility_id',
        'swimming_slot_id',
        'booking_datetime',
        'status'
    )
    def _check_capacity(self):
        for record in self:
            if record.status != 'confirmed':
                continue

            if record.booking_type == 'class' and record.class_schedule_id:
                capacity = record.class_schedule_id.facility_id.capacity

                confirmed_bookings = self.search_count([
                    ('id', '!=', record.id),
                    ('class_schedule_id', '=', record.class_schedule_id.id),
                    ('status', '=', 'confirmed'),
                ])

                if confirmed_bookings >= capacity:
                    raise ValidationError(
                        'This class is full. No more bookings can be confirmed.'
                    )

            elif record.booking_type == 'facility' and record.facility_id:
                confirmed_bookings = self.search_count([
                    ('id', '!=', record.id),
                    ('facility_id', '=', record.facility_id.id),
                    ('booking_type', '=', 'facility'),
                    ('booking_datetime', '=', record.booking_datetime),
                    ('status', '=', 'confirmed'),
                ])

                if confirmed_bookings >= record.facility_id.capacity:
                    raise ValidationError(
                        'This facility is full. No more bookings can be confirmed.'
                    )