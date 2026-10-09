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
        "start_datetime",
        "end_datetime",
        "state",
    )
    def _check_trainer_booking(self):
        for booking in self:
            if booking.state == "cancelled":
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

            if membership.remaining_pt_sessions <= 0:
                raise ValidationError(
                    "This membership has no remaining personal training sessions."
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

            booking._check_membership()
            booking._check_booking_conflict()
            booking._check_subscriber_conflict()
            booking._check_trainer_availability()

            booking.membership_id.used_pt_sessions += 1
            booking.state = "confirmed"

        return True

    def action_cancel(self):
        for booking in self:

            if booking.state == "confirmed":
                if booking.membership_id.used_pt_sessions > 0:
                    booking.membership_id.used_pt_sessions -= 1

            booking.state = "cancelled"

        return True