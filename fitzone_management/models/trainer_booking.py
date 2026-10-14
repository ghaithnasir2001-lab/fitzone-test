from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneTrainerBooking(models.Model):
    _name = "fitzone.trainer.booking"
    _description = "FitZone Trainer Booking"
    _order = "start_datetime"

    name = fields.Char(
        string="Booking Reference",
        required=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "fitzone.trainer.booking"
        ) or "New",
        copy=False,
    )

    trainer_id = fields.Many2one(
        "fitzone.trainer",
        string="Trainer",
        required=True,
        ondelete="cascade",
    )

    subscriber_id = fields.Many2one(
        "res.partner",
        string="Subscriber",
        required=True,
        domain=[("is_fitzone_subscriber", "=", True)],
        ondelete="restrict",
    )

    membership_id = fields.Many2one(
        "fitzone.membership.subscription",
        string="Membership",
        required=True,
        ondelete="restrict",
        domain="[('subscriber_id', '=', subscriber_id)]",
    )

    currency_id = fields.Many2one(
        related="membership_id.currency_id",
        readonly=True,
    )

    session_type = fields.Selection(
        [
            ("included", "Included Session"),
            ("paid_extra", "Paid Extra Session"),
        ],
        string="Session Type",
        required=True,
        default="included",
    )

    session_price = fields.Monetary(
        string="Extra Session Price",
        currency_field="currency_id",
        readonly=True,
        copy=False,
        default=0.0,
    )

    invoice_id = fields.Many2one(
        "account.move",
        string="Customer Invoice",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    invoice_payment_state = fields.Selection(
        related="invoice_id.payment_state",
        string="Invoice Payment Status",
        readonly=True,
    )

    start_datetime = fields.Datetime(
        string="Start Time",
        required=True,
    )

    end_datetime = fields.Datetime(
        string="End Time",
        required=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("attended", "Attended"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    notes = fields.Text(string="Notes")

    @api.constrains(
        "trainer_id",
        "subscriber_id",
        "membership_id",
        "session_type",
        "start_datetime",
        "end_datetime",
        "state",
    )
    def _check_trainer_booking(self):
        for booking in self:
            if booking.state in ("cancelled", "attended"):
                continue

            if not booking.start_datetime or not booking.end_datetime:
                continue

            if booking.end_datetime <= booking.start_datetime:
                raise ValidationError(
                    "End time must be later than start time."
                )

            if not booking.trainer_id.active:
                raise ValidationError(
                    "This trainer is not available for booking."
                )

            if booking.state in ("draft", "confirmed"):
                booking._check_membership()
            booking._check_booking_conflict()
            booking._check_subscriber_conflict()
            booking._check_trainer_availability()

    def _check_membership(self):
        for booking in self:
            membership = booking.membership_id

            if not membership:
                raise ValidationError(
                    "A membership is required for personal training."
                )

            if membership.subscriber_id != booking.subscriber_id:
                raise ValidationError(
                    "The selected membership does not belong to this subscriber."
                )

            if membership.status != "active":
                raise ValidationError(
                    "The membership must be active."
                )

            booking_date = fields.Datetime.to_datetime(
                booking.start_datetime
            ).date()

            if (
                membership.activation_date
                and booking_date < membership.activation_date
            ):
                raise ValidationError(
                    "The booking date is before the membership activation date."
                )

            if (
                membership.expiration_date
                and booking_date > membership.expiration_date
            ):
                raise ValidationError(
                    "The booking date is after the membership expiration date."
                )

            if (
                booking.session_type == "included"
                and membership.remaining_pt_sessions <= 0
            ):
                raise ValidationError(
                    "No included PT sessions remain. "
                    "Select Paid Extra Session instead."
                )

    def _check_booking_conflict(self):
        for booking in self:
            conflicting_booking = self.search(
                [
                    ("id", "!=", booking.id),
                    ("trainer_id", "=", booking.trainer_id.id),
                    ("state", "!=", "cancelled"),
                    ("start_datetime", "<", booking.end_datetime),
                    ("end_datetime", ">", booking.start_datetime),
                ],
                limit=1,
            )

            if conflicting_booking:
                raise ValidationError(
                    "This trainer already has a booking during this time."
                )

    def _check_subscriber_conflict(self):
        for booking in self:

            # Check conflicts with other personal training bookings
            conflicting_trainer_booking = self.search(
                [
                    ("id", "!=", booking.id),
                    ("subscriber_id", "=", booking.subscriber_id.id),
                    ("state", "!=", "cancelled"),
                    ("start_datetime", "<", booking.end_datetime),
                    ("end_datetime", ">", booking.start_datetime),
                ],
                limit=1,
            )

            if conflicting_trainer_booking:
                raise ValidationError(
                    "This subscriber already has another booking during this time."
                )

            # Check conflicts with class/facility bookings
            conflicting_booking = self.env["fitzone.booking"].search(
                [
                    ("subscriber_id", "=", booking.subscriber_id.id),
                    ("status", "!=", "cancelled"),
                    ("start_datetime", "<", booking.end_datetime),
                    ("end_datetime", ">", booking.start_datetime),
                ],
                limit=1,
            )

            if conflicting_booking:
                raise ValidationError(
                    "This subscriber already has another booking during this time."
                )

            # Check conflicts with nutrition consultations.
            conflicting_consultation = self.env[
                "fitzone.nutrition.consultation"
            ].search(
                [
                    ("subscriber_id", "=", booking.subscriber_id.id),
                    ("state", "!=", "cancelled"),
                    ("start_datetime", "<", booking.end_datetime),
                    ("end_datetime", ">", booking.start_datetime),
                ],
                limit=1,
            )

            if conflicting_consultation:
                raise ValidationError(
                    "This subscriber already has another booking during this time."
                )

    def _check_trainer_availability(self):
        for booking in self:

            # Convert booking start time to the user's local timezone
            booking_date = fields.Datetime.context_timestamp(
                booking,
                booking.start_datetime,
            )

            # Python weekday:
            # Monday = 0 ... Sunday = 6
            #
            # FitZone weekly schedule:
            # Sunday = 0 ... Saturday = 6
            day_of_week = str((booking_date.weekday() + 1) % 7)

            # Find the trainer's recurring working schedule
            schedules = self.env["fitzone.trainer.schedule"].search(
                [
                    ("trainer_id", "=", booking.trainer_id.id),
                    ("day_of_week", "=", day_of_week),
                    ("active", "=", True),
                ]
            )

            if not schedules:
                raise ValidationError(
                    "The trainer is not available on this day."
                )

            # Convert booking start time to decimal hours
            start_hour = (
                booking_date.hour
                + booking_date.minute / 60
            )

            # Convert booking end time to the user's local timezone
            end_date = fields.Datetime.context_timestamp(
                booking,
                booking.end_datetime,
            )

            # Convert booking end time to decimal hours
            end_hour = (
                end_date.hour
                + end_date.minute / 60
            )

            # Check whether at least one working schedule
            # fully covers the booking time
            available = any(
                schedule.start_time <= start_hour
                and schedule.end_time >= end_hour
                for schedule in schedules
            )

            if not available:
                raise ValidationError(
                    "The trainer is not available during this time."
                )

    def action_confirm(self):
        for booking in self:
            if booking.state != "draft":
                continue

            if booking.session_type == "paid_extra":
                price = float(
                    booking.env["ir.config_parameter"].sudo().get_param(
                        "fitzone_management.trainer_pt_session_price",
                        default=0.0,
                    )
                )
                if price <= 0:
                    raise ValidationError(
                        "The manager must configure an extra PT session "
                        "price greater than zero in FitZone settings."
                    )
                booking.session_price = price

            booking._check_membership()
            booking._check_booking_conflict()
            booking._check_subscriber_conflict()
            booking._check_trainer_availability()
            booking.state = "confirmed"

        return True

    def action_mark_attended(self):
        for booking in self:
            if booking.state != "confirmed":
                raise ValidationError(
                    "Only confirmed bookings can be marked as attended."
                )

            # Attendance can only be recorded after the booked session ends.
            if fields.Datetime.to_datetime(
                booking.end_datetime
            ) > fields.Datetime.now():
                raise ValidationError(
                    "A booking cannot be marked attended before its end time."
                )

            # Validate the membership at attendance.
            booking._check_membership()

            if booking.session_type == "included":
                booking.membership_id.used_pt_sessions += 1
            else:
                if not booking.invoice_id:
                    raise ValidationError(
                        "Create an invoice for the paid extra session "
                        "before marking it as attended."
                    )

            booking.state = "attended"

        return True

    def action_create_invoice(self):
        self.ensure_one()

        if self.session_type != "paid_extra":
            raise ValidationError(
                "Only paid extra sessions require an invoice."
            )

        if self.state != "confirmed":
            raise ValidationError(
                "Confirm the booking before creating its invoice."
            )

        if self.invoice_id:
            raise ValidationError(
                "An invoice already exists for this session."
            )

        if self.session_price <= 0:
            raise ValidationError(
                "The extra PT session price must be greater than zero."
            )

        company = self.env.company

        income_account = self.env["account.account"].search([
            ("company_ids", "in", [company.id]),
            ("account_type", "in", ["income", "income_other"]),
        ], limit=1)

        if not income_account:
            raise ValidationError(
                "No income account is configured for this company."
            )

        tax = self.env["account.tax"].search([
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 16.0),
            ("active", "=", True),
        ], limit=1)

        if not tax:
            raise ValidationError(
                "The active 16% sales tax was not found for this company."
            )

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.subscriber_id.id,
            "company_id": company.id,
            "invoice_date": fields.Date.context_today(self),
            "invoice_line_ids": [
                fields.Command.create({
                    "name": f"{self.name} - Extra Personal Training Session",
                    "quantity": 1.0,
                    # The configured session price includes 16% tax.
                    "price_unit": self.session_price / 1.16,
                    "account_id": income_account.id,
                    "tax_ids": [fields.Command.set([tax.id])],
                }),
            ],
        })

        invoice.action_post()
        self.invoice_id = invoice.id

        return {
            "type": "ir.actions.act_window",
            "name": "PT Session Invoice",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_cancel(self):
        for booking in self:
            if booking.state == "attended":
                raise ValidationError(
                    "An attended booking cannot be cancelled."
                )

            if booking.state == "cancelled":
                continue

            # Cancellation does not consume or refund a session.
            booking.state = "cancelled"

        return True
