
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    # Booking Price and Invoice

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )

    price = fields.Monetary(
        string='Booking Price',
        currency_field='currency_id',
        default=0.0,
        readonly=True
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Customer Invoice',
        readonly=True,
        copy=False,
        ondelete='restrict'
    )

    invoice_state = fields.Selection(
        related='invoice_id.state',
        string='Invoice Status',
        readonly=True
    )

    @api.onchange('booking_type', 'swimming_slot_id')
    def _onchange_booking_price(self):
        for record in self:
            if (
                record.booking_type == 'swimming'
                and record.swimming_slot_id
            ):
                record.price = record.swimming_slot_id.price
            else:
                record.price = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('booking_type') == 'swimming':
                slot = self.env['fitzone.swimming.slot'].browse(
                    vals.get('swimming_slot_id')
                )
                vals['price'] = (
                    slot.price if slot.exists() else 0.0
                )
            else:
                vals['price'] = 0.0

        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)

        if 'booking_type' in vals or 'swimming_slot_id' in vals:
            for record in self:
                if (
                    record.booking_type == 'swimming'
                    and record.swimming_slot_id
                ):
                    new_price = record.swimming_slot_id.price
                else:
                    new_price = 0.0

                super(FitZoneBooking, record).write({
                    'price': new_price
                })

        return result
    def action_create_invoice(self):
        self.ensure_one()

        if self.booking_type != 'swimming' or self.price <= 0:
            raise UserError(
                'Invoices can only be created for paid swimming bookings.'
            )

        if self.invoice_id:
            raise UserError(
                'An invoice already exists for this booking.'
            )

        if not self.subscriber_id:
            raise UserError(
                'Please select a subscriber before creating the invoice.'
            )

        company = self.company_id

        # Find a sales income account for this company.
        income_account = self.env['account.account'].search([
            ('company_ids', 'in', company.id),
            ('account_type', 'in', ['income', 'income_other']),
        ], limit=1)

        if not income_account:
            raise UserError(
                'No income account was found for this company. '
                'Please configure the chart of accounts first.'
            )

        # Find the 16% sales tax for this company.
        sales_tax = self.env['account.tax'].search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 16.0),
            ('amount_type', '=', 'percent'),
            ('active', '=', True),
        ], limit=1)

        if not sales_tax:
            raise UserError(
                'The 16% sales tax was not found for this company. '
                'Please configure the sales tax before creating the invoice.'
            )

        # The booking price includes 16% tax.
        price_without_tax = self.price / 1.16

        invoice = self.env['account.move'].with_company(company).create({
            'move_type': 'out_invoice',
            'partner_id': self.subscriber_id.id,
            'company_id': company.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [
                fields.Command.create({
                    'name': f'Swimming Booking - {self.name}',
                    'quantity': 1,
                    'price_unit': price_without_tax,
                    'account_id': income_account.id,
                    'tax_ids': [fields.Command.set([sales_tax.id])],
                }),
            ],
        })

        self.invoice_id = invoice.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

    def action_view_invoice(self):
        self.ensure_one()

        if not self.invoice_id:
            raise UserError('There is no invoice linked to this booking.')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
            'target': 'current',
        }
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

    @api.constrains(
        'subscriber_id', 'start_datetime', 'end_datetime', 'status'
    )
    def _check_subscriber_appointment_overlap(self):
        for record in self:
            if record.status == 'cancelled':
                continue
            if not record.subscriber_id or not record.start_datetime or not record.end_datetime:
                continue

            same_model_domain = [
                ('id', '!=', record.id),
                ('subscriber_id', '=', record.subscriber_id.id),
                ('status', '!=', 'cancelled'),
                ('start_datetime', '<', record.end_datetime),
                ('end_datetime', '>', record.start_datetime),
            ]

            if self.search_count(same_model_domain, limit=1):
                raise ValidationError(
                    'This subscriber already has another booking during this time.'
                )

            overlap_domain = [
                ('subscriber_id', '=', record.subscriber_id.id),
                ('state', '!=', 'cancelled'),
                ('start_datetime', '<', record.end_datetime),
                ('end_datetime', '>', record.start_datetime),
            ]

            if self.env['fitzone.trainer.booking'].search_count(
                overlap_domain, limit=1
            ):
                raise ValidationError(
                    'This subscriber already has another booking during this time.'
                )

            if self.env['fitzone.nutrition.consultation'].search_count([
                ('subscriber_id', '=', record.subscriber_id.id),
                ('state', '!=', 'cancelled'),
                ('start_datetime', '<', record.end_datetime),
                ('end_datetime', '>', record.start_datetime),
            ], limit=1):
                raise ValidationError(
                    'This subscriber already has another booking during this time.'
                )
