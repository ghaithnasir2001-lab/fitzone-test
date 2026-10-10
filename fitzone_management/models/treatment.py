from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneTreatment(models.Model):
    _name = 'fitzone.treatment'
    _description = 'FitZone Treatment'
    _order = 'id desc'

    name = fields.Char(
        string='Treatment Reference',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env[
            'ir.sequence'
        ].next_by_code('fitzone.treatment') or 'New',
    )

    rehab_file_id = fields.Many2one(
        'fitzone.rehab.file',
        string='Rehabilitation File',
        required=True,
        ondelete='restrict',
    )

    physiotherapist_id = fields.Many2one(
        'hr.employee',
        string='Physiotherapist',
        required=True,
        ondelete='restrict',
    )

    booking_id = fields.Many2one(
        'fitzone.booking',
        string='Booking',
        required=True,
        ondelete='restrict',
    )

    treatment_type = fields.Char(
        string='Treatment Type',
    )

    description = fields.Text(
        string='Description',
    )

    duration_minutes = fields.Integer(
        string='Duration (Minutes)',
    )

    notes = fields.Text(
        string='Notes',
    )

    state = fields.Selection(
        [
            ('scheduled', 'Scheduled'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='scheduled',
        copy=False,
    )

    @api.constrains('physiotherapist_id', 'rehab_file_id')
    def _check_physiotherapist(self):
        for record in self:
            if (
                record.physiotherapist_id
                and record.physiotherapist_id.fitzone_staff_type
                != 'physiotherapist'
            ):
                raise ValidationError(
                    'The selected employee must be a Physiotherapist.'
                )

            if (
                record.rehab_file_id
                and record.physiotherapist_id
                and record.rehab_file_id.physiotherapist_id
                != record.physiotherapist_id
            ):
                raise ValidationError(
                    'The treatment physiotherapist must match the rehabilitation file physiotherapist.'
                )

    @api.constrains('rehab_file_id', 'booking_id')
    def _check_booking_subscriber(self):
        for record in self:
            if not record.rehab_file_id or not record.booking_id:
                continue

            if record.booking_id.booking_type != 'physiotherapy':
                raise ValidationError(
                    'Treatment bookings must be Physiotherapy bookings.'
                )

            if (
                record.booking_id.subscriber_id
                != record.rehab_file_id.partner_id
            ):
                raise ValidationError(
                    'The treatment booking must belong to the rehabilitation file subscriber.'
                )

    @api.constrains('duration_minutes')
    def _check_duration(self):
        for record in self:
            if record.duration_minutes < 0:
                raise ValidationError(
                    'Treatment duration cannot be negative.'
                )

    def action_complete(self):
        for record in self:

            if record.state == 'cancelled':
                raise ValidationError(
                    'A cancelled treatment cannot be completed.'
                )

            if record.state == 'completed':
                continue

            usage_date = (
                fields.Datetime.to_datetime(
                    record.booking_id.start_datetime
                ).date()
                if record.booking_id
                and record.booking_id.start_datetime
                else fields.Date.context_today(record)
            )

            subscription = self.env[
                'fitzone.membership.subscription'
            ].search(
                [
                    (
                        'subscriber_id',
                        '=',
                        record.rehab_file_id.partner_id.id,
                    ),
                    (
                        'activation_date',
                        '<=',
                        usage_date,
                    ),
                    (
                        'expiration_date',
                        '>=',
                        usage_date,
                    ),
                    (
                        'status',
                        '!=',
                        'cancelled',
                    ),
                    (
                        'package_id.included_physio_sessions_per_month',
                        '>',
                        0,
                    ),
                ],
                order='activation_date desc, id desc',
                limit=1,
            )

            if subscription:

                period_start, period_end = (
                    subscription._get_physio_period(
                        usage_date
                    )
                )

                if period_start and period_end:

                    used_sessions = (
                        subscription
                        ._count_completed_physio_treatments(
                            period_start,
                            period_end,
                        )
                    )

                    monthly_allowance = (
                        subscription.package_id
                        .included_physio_sessions_per_month
                    )

                    if used_sessions >= monthly_allowance:
                        raise ValidationError(
                            'The subscriber has used all included '
                            'physiotherapy sessions for this '
                            'membership month. '
                            'Unused sessions do not roll over.'
                        )

            record.state = 'completed'

    def action_cancel(self):
        for record in self:
            if record.state == 'completed':
                raise ValidationError(
                    'A completed treatment cannot be cancelled.'
                )
            record.state = 'cancelled'

    def action_reset_to_scheduled(self):
        for record in self:
            if record.state == 'completed':
                raise ValidationError(
                    'A completed treatment cannot be reset to scheduled.'
                )
            record.state = 'scheduled'
