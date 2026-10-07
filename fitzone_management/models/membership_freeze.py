from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneMembershipFreeze(models.Model):
    _name = 'fitzone.membership.freeze'
    _description = 'FitZone Membership Freeze'
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string='Freeze Reference',
        required=True,
        copy=False,
        default='New',
    )

    subscription_id = fields.Many2one(
        'fitzone.membership.subscription',
        string='Membership Subscription',
        required=True,
        ondelete='cascade',
    )

    subscriber_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        related='subscription_id.subscriber_id',
        store=True,
        readonly=True,
    )

    request_date = fields.Date(
        string='Request Date',
        required=True,
        default=fields.Date.context_today,
    )

    start_date = fields.Date(
        string='Freeze Start Date',
        required=True,
    )

    freeze_days = fields.Integer(
        string='Requested Freeze Days',
        required=True,
    )

    actual_freeze_days = fields.Integer(
        string='Actual Freeze Days',
        default=0,
        readonly=True,
        copy=False,
    )

    end_date = fields.Date(
        string='Freeze End Date',
        compute='_compute_end_date',
        store=True,
    )

    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='draft',
    )

    notes = fields.Text(
        string='Notes',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'fitzone.membership.freeze'
                ) or 'New'

        return super().create(vals_list)

    @api.depends('start_date', 'freeze_days')
    def _compute_end_date(self):
        for record in self:
            if record.start_date and record.freeze_days > 0:
                record.end_date = (
                    record.start_date
                    + relativedelta(days=record.freeze_days - 1)
                )
            else:
                record.end_date = False

    @api.constrains(
        'subscription_id',
        'request_date',
        'start_date',
        'freeze_days',
    )
    def _check_freeze_dates(self):
        for record in self:

            if record.freeze_days <= 0:
                raise ValidationError(
                    'Freeze days must be greater than zero.'
                )

            subscription = record.subscription_id

            if not subscription:
                continue

            if subscription.status not in ('active', 'frozen'):
                raise ValidationError(
                    'Freeze can only be requested for an active membership.'
                )

            if (
                record.start_date
                and subscription.activation_date
                and record.start_date < subscription.activation_date
            ):
                raise ValidationError(
                    'Freeze cannot start before the membership activation date.'
                )

            if (
                record.start_date
                and subscription.expiration_date
            ):
                grace_period_end = (
                    subscription.expiration_date
                    + relativedelta(months=2)
                )

                if record.start_date > grace_period_end:
                    raise ValidationError(
                        'Freeze can only be used during the membership '
                        'period or within two months after expiration.'
                    )

    @api.constrains('subscription_id', 'freeze_days')
    def _check_freeze_allowance(self):
        for record in self:

            if not record.subscription_id:
                continue

            other_freezes = self.search([
                ('subscription_id', '=', record.subscription_id.id),
                ('id', '!=', record.id),
                ('status', '!=', 'cancelled'),
            ])

            used_days = sum(
                other_freezes.mapped('actual_freeze_days')
            )

            if used_days + record.freeze_days > (
                record.subscription_id.allowed_freeze_days
            ):
                raise ValidationError(
                    'Total freeze days cannot exceed the allowed freeze '
                    'days for this membership.'
                )

    def action_apply_freeze(self):
        for record in self:

            if record.status != 'draft':
                raise ValidationError(
                    'Only draft freeze requests can be applied.'
                )

            if record.freeze_days <= 0:
                raise ValidationError(
                    'Freeze days must be greater than zero.'
                )

            subscription = record.subscription_id

            if not subscription:
                raise ValidationError(
                    'Membership subscription is required.'
                )

            if subscription.status != 'active':
                raise ValidationError(
                    'Only active memberships can be frozen.'
                )

            if record.freeze_days > subscription.remaining_freeze_days:
                raise ValidationError(
                    'Freeze days exceed the remaining freeze allowance.'
                )

            if not subscription.expiration_date:
                raise ValidationError(
                    'Membership expiration date is required before applying '
                    'a freeze.'
                )

            grace_period_end = (
                subscription.expiration_date
                + relativedelta(months=2)
            )

            if record.start_date > grace_period_end:
                raise ValidationError(
                    'Freeze can only be applied during the membership '
                    'period or within two months after expiration.'
                )

            subscription.expiration_date = (
                subscription.expiration_date
                + relativedelta(days=record.freeze_days)
            )

            # Initially no days are considered permanently consumed.
            # They are calculated when the freeze is resumed or completed.
            record.actual_freeze_days = 0

            subscription.status = 'frozen'
            record.status = 'active'

        return True

    @api.model
    def _cron_complete_expired_freezes(self):
        today = fields.Date.context_today(self)

        expired_freezes = self.search([
            ('status', '=', 'active'),
            ('end_date', '<', today),
        ])

        for freeze in expired_freezes:
            subscription = freeze.subscription_id

            # The full requested freeze period was used.
            freeze.actual_freeze_days = freeze.freeze_days
            freeze.status = 'completed'

            if subscription:
                if subscription.status == 'frozen':
                    subscription.used_freeze_days += (
                        freeze.actual_freeze_days
                    )

                    if (
                        subscription.expiration_date
                        and subscription.expiration_date < today
                    ):
                        subscription.status = 'expired'
                    else:
                        subscription.status = 'active'

        return True
