from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneBooking(models.Model):
    _name = 'fitzone.booking'
    _description = 'FitZone Booking'

    name = fields.Char(
        string='Booking Reference',
        required=True,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'fitzone.booking'
        ) or 'New',
        copy=False
    )

    booking_type = fields.Selection(
        [
            ('class', 'Class'),
            ('swimming', 'Swimming'),
            ('physiotherapy', 'Physiotherapy'),
        ],
        string='Booking Type',
        required=True
    )

    class_id = fields.Many2one(
        'fitzone.class',
        string='Class'
    )

    class_schedule_id = fields.Many2one(
        'fitzone.class.schedule',
        string='Class Schedule'
    )

    swimming_slot_id = fields.Many2one(
        'fitzone.swimming.slot',
        string='Swimming Slot'
    )

    physiotherapy_start_datetime = fields.Datetime(
        string='Physiotherapy Start Date & Time'
    )

    physiotherapy_end_datetime = fields.Datetime(
        string='Physiotherapy End Date & Time'
    )

    subscriber_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        required=True,
        domain=[('is_fitzone_subscriber', '=', True)]
    )

    start_datetime = fields.Datetime(
        string='Start Date & Time',
        compute='_compute_booking_datetime',
        store=True
    )

    end_datetime = fields.Datetime(
        string='End Date & Time',
        compute='_compute_booking_datetime',
        store=True
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

    @api.depends(
        'booking_type',
        'class_schedule_id.start_datetime',
        'class_schedule_id.end_datetime',
        'swimming_slot_id.start_datetime',
        'swimming_slot_id.end_datetime',
        'physiotherapy_start_datetime',
        'physiotherapy_end_datetime'
    )
    def _compute_booking_datetime(self):
        for record in self:
            record.start_datetime = False
            record.end_datetime = False

            if record.booking_type == 'class' and record.class_schedule_id:
                record.start_datetime = (
                    record.class_schedule_id.start_datetime
                )
                record.end_datetime = (
                    record.class_schedule_id.end_datetime
                )

            elif (
                record.booking_type == 'swimming'
                and record.swimming_slot_id
            ):
                record.start_datetime = (
                    record.swimming_slot_id.start_datetime
                )
                record.end_datetime = (
                    record.swimming_slot_id.end_datetime
                )

            elif record.booking_type == 'physiotherapy':
                record.start_datetime = (
                    record.physiotherapy_start_datetime
                )
                record.end_datetime = (
                    record.physiotherapy_end_datetime
                )

    @api.onchange('booking_type')
    def _onchange_booking_type(self):
        if self.booking_type == 'class':
            self.swimming_slot_id = False
            self.physiotherapy_start_datetime = False
            self.physiotherapy_end_datetime = False

        elif self.booking_type == 'swimming':
            self.class_id = False
            self.class_schedule_id = False
            self.physiotherapy_start_datetime = False
            self.physiotherapy_end_datetime = False

        elif self.booking_type == 'physiotherapy':
            self.class_id = False
            self.class_schedule_id = False
            self.swimming_slot_id = False

    @api.constrains(
        'booking_type',
        'class_id',
        'class_schedule_id',
        'swimming_slot_id'
    )
    def _check_booking_details(self):
        for record in self:

            if record.booking_type == 'class':

                if not record.class_id or not record.class_schedule_id:
                    raise ValidationError(
                        'Class bookings must have a class and a class schedule.'
                    )

                if record.swimming_slot_id:
                    raise ValidationError(
                        'Class bookings cannot have a swimming slot.'
                    )

                if record.class_schedule_id.class_id != record.class_id:
                    raise ValidationError(
                        'The selected class schedule must belong to the selected class.'
                    )

                facility = record.class_schedule_id.facility_id

                if facility.booking_method != 'class_schedule':
                    raise ValidationError(
                        'The selected facility must use Class Schedule booking.'
                    )

            elif record.booking_type == 'swimming':

                if not record.swimming_slot_id:
                    raise ValidationError(
                        'Swimming bookings must have a swimming slot.'
                    )

                if record.class_id:
                    raise ValidationError(
                        'Swimming bookings cannot have a class.'
                    )

                if record.class_schedule_id:
                    raise ValidationError(
                        'Swimming bookings cannot have a class schedule.'
                    )

                facility = record.swimming_slot_id.facility_id

                if facility.booking_method != 'swimming_slot':
                    raise ValidationError(
                        'The selected facility must use Swimming Slot booking.'
                    )

                if facility.state != 'available':
                    raise ValidationError(
                        'This swimming pool is not available for booking.'
                    )

            elif record.booking_type == 'physiotherapy':
                if not record.physiotherapy_start_datetime:
                    raise ValidationError(
                        'Physiotherapy bookings must have a start date and time.'
                    )

                if not record.physiotherapy_end_datetime:
                    raise ValidationError(
                        'Physiotherapy bookings must have an end date and time.'
                    )

                if (
                    record.physiotherapy_end_datetime
                    <= record.physiotherapy_start_datetime
                ):
                    raise ValidationError(
                        'The physiotherapy end date and time must be after the start date and time.'
                    )

    @api.constrains(
        'booking_type',
        'class_schedule_id',
        'status'
    )
    def _check_class_schedule_facility_availability(self):
        for record in self:
            if (
                record.status == 'cancelled'
                or record.booking_type != 'class'
                or not record.class_schedule_id
            ):
                continue

            facility = record.class_schedule_id.facility_id

            if facility.booking_method != 'class_schedule':
                raise ValidationError(
                    'This facility must use Class Schedule booking.'
                )

            if facility.state != 'available':
                raise ValidationError(
                    'This class schedule cannot be booked because its facility is not available.'
                )

    @api.constrains(
        'booking_type',
        'swimming_slot_id',
        'status'
    )
    def _check_swimming_slot(self):
        for record in self:
            if (
                record.status == 'cancelled'
                or record.booking_type != 'swimming'
                or not record.swimming_slot_id
            ):
                continue

            facility = record.swimming_slot_id.facility_id

            if facility.booking_method != 'swimming_slot':
                raise ValidationError(
                    'The selected facility must use Swimming Slot booking.'
                )

            if facility.state != 'available':
                raise ValidationError(
                    'This swimming slot cannot be booked because its facility is not available.'
                )

    @api.constrains(
        'subscriber_id',
        'booking_type',
        'class_schedule_id',
        'status'
    )
    def _check_duplicate_class_booking(self):
        for record in self:
            if (
                record.status == 'cancelled'
                or record.booking_type != 'class'
                or not record.subscriber_id
                or not record.class_schedule_id
            ):
                continue

            duplicate_booking = self.search([
                ('id', '!=', record.id),
                ('subscriber_id', '=', record.subscriber_id.id),
                ('booking_type', '=', 'class'),
                ('class_schedule_id', '=', record.class_schedule_id.id),
                ('status', '!=', 'cancelled'),
            ], limit=1)

            if duplicate_booking:
                raise ValidationError(
                    'This subscriber already has a booking for this class schedule.'
                )

    @api.constrains(
        'subscriber_id',
        'booking_type',
        'swimming_slot_id',
        'status'
    )
    def _check_duplicate_swimming_booking(self):
        for record in self:
            if (
                record.status == 'cancelled'
                or record.booking_type != 'swimming'
                or not record.subscriber_id
                or not record.swimming_slot_id
            ):
                continue

            duplicate_booking = self.search([
                ('id', '!=', record.id),
                ('subscriber_id', '=', record.subscriber_id.id),
                ('booking_type', '=', 'swimming'),
                ('swimming_slot_id', '=', record.swimming_slot_id.id),
                ('status', '!=', 'cancelled'),
            ], limit=1)

            if duplicate_booking:
                raise ValidationError(
                    'This subscriber already has a booking for this swimming slot.'
                )

    @api.constrains(
        'booking_type',
        'class_schedule_id',
        'swimming_slot_id',
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

            elif record.booking_type == 'swimming' and record.swimming_slot_id:
                capacity = record.swimming_slot_id.facility_id.capacity

                confirmed_bookings = self.search_count([
                    ('id', '!=', record.id),
                    ('swimming_slot_id', '=', record.swimming_slot_id.id),
                    ('status', '=', 'confirmed'),
                ])

                if confirmed_bookings >= capacity:
                    raise ValidationError(
                        'This swimming slot is full. No more bookings can be confirmed.'
                    )