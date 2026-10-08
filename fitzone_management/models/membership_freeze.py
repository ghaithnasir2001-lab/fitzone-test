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

    applied_freeze_days = fields.Integer(
        string='Applied Freeze Days',
        default=0,
        readonly=True,
        copy=False,
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



    @api.depends(
        'start_date',
        'freeze_days',
        'applied_freeze_days',
        'status',
    )
    def _compute_end_date(self):
        for record in self:

            effective_days = (
                record.applied_freeze_days
                if record.applied_freeze_days
                else record.freeze_days
            )

            if record.start_date and effective_days > 0:
                record.end_date = (
                    record.start_date
                    + relativedelta(days=effective_days - 1)
                )
            else:
                record.end_date = False



    @api.constrains(
        'start_date',
        'freeze_days',
        'subscription_id',
    )
    def _check_freeze_dates(self):
        for record in self:

            if record.freeze_days <= 0:
                raise ValidationError(
                    'Requested freeze days must be greater than zero.'
                )

            subscription = record.subscription_id

            if not subscription:
                continue

            if subscription.status not in ('active', 'frozen'):
                raise ValidationError(
                    'Freeze can only be requested for an active or frozen '
                    'membership.'
                )

            if not subscription.activation_date:
                raise ValidationError(
                    'The membership must have an activation date.'
                )

            if record.start_date < subscription.activation_date:
                raise ValidationError(
                    'Freeze start date cannot be before the membership '
                    'activation date.'
                )

    @api.constrains(
        'applied_freeze_days',
        'subscription_id',
    )
    def _check_applied_freeze_allowance(self):
        for record in self:

            if not record.subscription_id:
                continue

            if record.applied_freeze_days <= 0:
                continue

            other_freezes = self.search(
                [
                    ('subscription_id', '=', record.subscription_id.id),
                    ('id', '!=', record.id),
                    ('status', '!=', 'cancelled'),
                ]
            )

            used_or_applied = sum(
                freeze.actual_freeze_days
                if freeze.status == 'completed'
                else freeze.applied_freeze_days
                for freeze in other_freezes
            )

            if (
                used_or_applied + record.applied_freeze_days
                > record.subscription_id.allowed_freeze_days
            ):
                raise ValidationError(
                    'Applied freeze days cannot exceed the membership '
                    'freeze allowance.'
                )


    def action_apply_freeze(self):
        for record in self:
            if record.status != 'draft':
                raise ValidationError(
                    'Only draft freeze requests can be applied.'
                )

            subscription = record.subscription_id

            if not subscription:
                raise ValidationError(
                    'A membership subscription is required.'
                )

            if subscription.status != 'active':
                raise ValidationError(
                    'Freeze can only be applied to an active membership.'
                )

            if not subscription.expiration_date:
                raise ValidationError(
                    'The membership must have an expiration date.'
                )

            if record.start_date > subscription.expiration_date:
                raise ValidationError(
                    'Freeze start date cannot be after the membership expiration date.'
                )

            remaining_membership_days = (
                subscription.expiration_date - record.start_date
            ).days + 1

            if remaining_membership_days <= 0:
                raise ValidationError(
                    'There are no remaining membership days available '
                    'for this freeze.'
                )

            remaining_freeze_days = (
                subscription.remaining_freeze_days
            )

            if remaining_freeze_days <= 0:
                raise ValidationError(
                    'No freeze days remain for this membership.'
                )

            if record.freeze_days > remaining_membership_days or record.freeze_days > remaining_freeze_days:
                raise ValidationError(
                    f'Requested freeze days ({record.freeze_days}) cannot exceed available membership days ({remaining_membership_days}) or remaining freeze allowance ({remaining_freeze_days}).'
                )

            applicable_freeze_days = min(
                record.freeze_days,
                remaining_freeze_days,
                remaining_membership_days,
            )

            if applicable_freeze_days <= 0:
                raise ValidationError(
                    'The calculated freeze duration must be greater than zero.'
                )

            record.applied_freeze_days = applicable_freeze_days
            record.actual_freeze_days = 0

            subscription.expiration_date = (
                subscription.expiration_date
                + relativedelta(days=applicable_freeze_days)
            )

            subscription.status = 'frozen'
            record.status = 'active'
        return True


    @api.model
    def _cron_complete_expired_freezes(self):
        today = fields.Date.context_today(self)

        freezes = self.search(
            [
                ('status', '=', 'active'),
                ('end_date', '<', today),
            ]
        )

        for freeze in freezes:

            if freeze.applied_freeze_days <= 0:
                freeze.status = 'completed'
                continue

            freeze.actual_freeze_days = freeze.applied_freeze_days
            freeze.status = 'completed'

            subscription = freeze.subscription_id

            if not subscription:
                continue

            subscription.used_freeze_days += (
                freeze.applied_freeze_days
            )

            if (
                subscription.expiration_date
                and subscription.expiration_date < today
            ):
                subscription.status = 'expired'
            else:
                subscription.status = 'active'