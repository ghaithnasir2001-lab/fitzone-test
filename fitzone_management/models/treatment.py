from odoo import api, fields, models
from odoo.exceptions import ValidationError


def _get_physio_session_price(env):
    return float(
        env["ir.config_parameter"].sudo().get_param(
            "fitzone_management.physio_session_price",
            default=0.0,
        )
    )


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

    subscription_id = fields.Many2one(
        'fitzone.membership.subscription',
        string='Membership Subscription',
        readonly=True,
        copy=False,
        ondelete='restrict',
    )

    session_type = fields.Selection(
        [
            ('included', 'Included in Membership'),
            ('paid_extra', 'Paid Extra Session'),
        ],
        string='Session Type',
        required=True,
        default='included',
    )

    session_price = fields.Float(
        string='Session Price (JOD)',
        default=lambda self: _get_physio_session_price(self.env),
        readonly=True,
        copy=False,
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        readonly=True,
        copy=False,
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
                    'The treatment physiotherapist must match the '
                    'rehabilitation file physiotherapist.'
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
                    'The treatment booking must belong to the '
                    'rehabilitation file subscriber.'
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

            if record.session_type == 'paid_extra':
                if not record.invoice_id:
                    raise ValidationError(
                        'Create an invoice for the paid extra '
                        'physiotherapy session before completing it.'
                    )
                record.subscription_id = False
                record.state = 'completed'
                continue

            usage_date = (
                fields.Datetime.to_datetime(
                    record.booking_id.start_datetime
                ).date()
                if record.booking_id
                and record.booking_id.start_datetime
                else fields.Date.context_today(record)
            )

            subscriptions = self.env[
                'fitzone.membership.subscription'
            ].search(
                [
                    (
                        'subscriber_id',
                        '=',
                        record.rehab_file_id.partner_id.id,
                    ),
                    ('activation_date', '<=', usage_date),
                    ('expiration_date', '>=', usage_date),
                    ('status', '=', 'active'),
                    (
                        'package_id.included_physio_sessions_per_month',
                        '>',
                        0,
                    ),
                ],
                order='activation_date desc, id desc',
            )

            selected_subscription = False

            for subscription in subscriptions:
                period_start, period_end = (
                    subscription._get_physio_period(usage_date)
                )

                if not period_start or not period_end:
                    continue

                used_sessions = (
                    subscription._count_completed_physio_treatments(
                        period_start,
                        period_end,
                    )
                )

                monthly_allowance = (
                    subscription.package_id
                    .included_physio_sessions_per_month
                )

                if used_sessions < monthly_allowance:
                    selected_subscription = subscription
                    break

            if not selected_subscription:
                raise ValidationError(
                    'No included physiotherapy sessions are available. '
                    'Select Paid Extra Session and create its invoice '
                    'to complete this treatment.'
                )

            record.subscription_id = selected_subscription
            record.state = 'completed'

    def action_create_invoice(self):
        self.ensure_one()

        if self.session_type != 'paid_extra':
            raise ValidationError(
                'Only paid extra physiotherapy sessions require an invoice.'
            )

        if self.state != 'scheduled':
            raise ValidationError(
                'Create the invoice before completing the treatment.'
            )

        if self.invoice_id:
            raise ValidationError('An invoice already exists.')

        price = _get_physio_session_price(self.env)
        if price <= 0:
            raise ValidationError(
                'The manager must configure an extra physiotherapy '
                'session price greater than zero in FitZone settings.'
            )

        company = self.env.company
        income_account = self.env['account.account'].search([
            ('company_ids', 'in', [company.id]),
            ('account_type', 'in', ['income', 'income_other']),
        ], limit=1)

        if not income_account:
            raise ValidationError(
                'No income account is configured for this company.'
            )

        tax = self.env['account.tax'].search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 16.0),
            ('active', '=', True),
        ], limit=1)

        if not tax:
            raise ValidationError(
                'The active 16% sales tax was not found for this company.'
            )

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.rehab_file_id.partner_id.id,
            'company_id': company.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': [
                fields.Command.create({
                    'name': (
                        f'{self.name} - Extra Physiotherapy Session'
                    ),
                    'quantity': 1.0,
                    # Configured price includes 16% sales tax.
                    'price_unit': price / 1.16,
                    'account_id': income_account.id,
                    'tax_ids': [fields.Command.set([tax.id])],
                }),
            ],
        })

        invoice.action_post()
        self.write({
            'invoice_id': invoice.id,
            'session_price': price,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Physiotherapy Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

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
