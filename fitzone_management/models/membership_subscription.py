from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneMembershipSubscription(models.Model):
    _name = 'fitzone.membership.subscription'
    _description = 'FitZone Membership Subscription'
    _order = 'subscription_date desc, id desc'

    name = fields.Char(
        string='Subscription Reference',
        required=True,
        copy=False,
        default='New',
    )

    subscriber_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        required=True,
        domain=[('is_fitzone_subscriber', '=', True)],
    )

    package_id = fields.Many2one(
        'fitzone.membership.package',
        string='Membership Package',
        required=True,
        domain=[('active', '=', True)],
    )

    subscription_date = fields.Date(
        string='Subscription Date',
        required=True,
        default=fields.Date.context_today,
    )

    activation_date = fields.Date(
        string='Activation Date',
        required=True,
    )

    original_expiration_date = fields.Date(
        string='Original Expiration Date',
        required=True,
    )

    expiration_date = fields.Date(
        string='Expiration Date',
        required=True,
    )

    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('frozen', 'Frozen'),
            ('expired', 'Expired'),
            ('renewed', 'Renewed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='draft',
    )

    currency_id = fields.Many2one(
        related='package_id.currency_id',
        string='Currency',
        store=True,
    )

    price = fields.Monetary(
        string='Package Price',
        currency_field='currency_id',
        required=True,
    )

    discount = fields.Monetary(
        string='Discount',
        currency_field='currency_id',
        default=0.0,
    )

    final_price = fields.Monetary(
        string='Final Price',
        currency_field='currency_id',
        compute='_compute_final_price',
        store=True,
    )

    allowed_freeze_days = fields.Integer(
        string='Allowed Freeze Days',
        related='package_id.freeze_days',
        store=True,
    )

    used_freeze_days = fields.Integer(
        string='Used Freeze Days',
        default=0,
    )

    remaining_freeze_days = fields.Integer(
        string='Remaining Freeze Days',
        compute='_compute_remaining_freeze_days',
        store=True,
    )

    included_pt_sessions = fields.Integer(
        string='Included PT Sessions',
        related='package_id.included_pt_sessions',
        store=True,
    )

    used_pt_sessions = fields.Integer(
        string='Used PT Sessions',
        default=0,
    )

    remaining_pt_sessions = fields.Integer(
        string='Remaining PT Sessions',
        compute='_compute_remaining_pt_sessions',
        store=True,
    )

    included_physio_sessions = fields.Integer(
        string='Included Physiotherapy Sessions',
        compute='_compute_included_physio_sessions',
        store=True,
    )

    used_physio_sessions = fields.Integer(
        string='Used Physiotherapy Sessions',
        default=0,
    )

    remaining_physio_sessions = fields.Integer(
        string='Remaining Physiotherapy Sessions',
        compute='_compute_remaining_physio_sessions',
        store=True,
    )

    included_nutrition_consultations = fields.Integer(
        string='Included Nutrition Consultations',
        related='package_id.included_nutrition_consultations',
        store=True,
    )

    used_nutrition_consultations = fields.Integer(
        string='Used Nutrition Consultations',
        default=0,
    )

    remaining_nutrition_consultations = fields.Integer(
        string='Remaining Nutrition Consultations',
        compute='_compute_remaining_nutrition_consultations',
        store=True,
    )

    previous_subscription_id = fields.Many2one(
        'fitzone.membership.subscription',
        string='Previous Subscription',
        copy=False,
    )

    renewal_subscription_id = fields.Many2one(
        'fitzone.membership.subscription',
        string='Renewal Subscription',
        copy=False,
    )

    renewal_date = fields.Date(
        string='Renewal Date',
    )

    notes = fields.Text(
        string='Notes',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'fitzone.membership.subscription'
                ) or 'New'

            if vals.get('package_id'):
                package = self.env['fitzone.membership.package'].browse(
                    vals['package_id']
                )
                vals['price'] = package.price

            subscription_date = fields.Date.to_date(
                vals.get('subscription_date')
            ) or fields.Date.context_today(self)

            activation_date = fields.Date.to_date(
                vals.get('activation_date')
            ) or subscription_date

            vals['subscription_date'] = subscription_date
            vals['activation_date'] = activation_date

            if vals.get('package_id'):
                package = self.env['fitzone.membership.package'].browse(
                    vals['package_id']
                )

                expiration_date = (
                    activation_date
                    + relativedelta(months=package.duration_months)
                    - relativedelta(days=1)
                )

                vals['original_expiration_date'] = expiration_date
                vals['expiration_date'] = expiration_date

        records = super().create(vals_list)

        today = fields.Date.context_today(self)

        for record in records:
            if record.status in ('cancelled', 'renewed'):
                continue

            if record.activation_date and record.activation_date <= today:
                record.status = 'active'
            else:
                record.status = 'draft'

        return records

    def write(self, vals):
        result = super().write(vals)

        if 'activation_date' in vals or 'expiration_date' in vals:
            today = fields.Date.context_today(self)

            for record in self:
                if record.status in ('cancelled', 'renewed', 'frozen'):
                    continue

                if (
                    record.expiration_date
                    and record.expiration_date < today
                ):
                    record.status = 'expired'

                elif (
                    record.activation_date
                    and record.activation_date <= today
                ):
                    record.status = 'active'

                else:
                    record.status = 'draft'
        return result


    @api.onchange(
        'subscription_date',
        'package_id',
        'activation_date',
    )
    def _onchange_subscription_dates(self):
        for record in self:
            if not record.subscription_date:
                continue

            if not record.activation_date:
                record.activation_date = record.subscription_date

            if record.activation_date < record.subscription_date:
                record.activation_date = (
                    record._origin.activation_date
                    or record.subscription_date
                )

                raise ValidationError(
                    'Activation date cannot be before subscription date.'
                )

            if record.package_id:
                record.price = record.package_id.price

            if record.package_id and record.activation_date:
                expiration_date = (
                    record.activation_date
                    + relativedelta(
                        months=record.package_id.duration_months
                    )
                    - relativedelta(days=1)
                )

                record.original_expiration_date = expiration_date
                record.expiration_date = expiration_date

    @api.onchange(
        'discount',
        'used_freeze_days',
        'used_pt_sessions',
        'used_physio_sessions',
        'used_nutrition_consultations',
    )
    def _onchange_non_negative_values(self):
        for record in self:

            if record.discount < 0:
                record.discount = 0.0
                raise ValidationError(
                    'Discount cannot be negative.'
                )

            if record.used_freeze_days < 0:
                record.used_freeze_days = 0
                raise ValidationError(
                    'Used freeze days cannot be negative.'
                )

            if record.used_freeze_days > record.allowed_freeze_days:
                record.used_freeze_days = (
                    record._origin.used_freeze_days
                    if record._origin
                    else 0
                )

                raise ValidationError(
                    'Used freeze days cannot exceed the allowed freeze days.'
                )

            if record.used_pt_sessions < 0:
                record.used_pt_sessions = 0
                raise ValidationError(
                    'Used PT sessions cannot be negative.'
                )

            if record.used_pt_sessions > record.included_pt_sessions:
                record.used_pt_sessions = (
                    record._origin.used_pt_sessions
                    if record._origin
                    else 0
                )

                raise ValidationError(
                    'Used PT sessions cannot exceed included PT sessions.'
                )

            if record.used_physio_sessions < 0:
                record.used_physio_sessions = 0
                raise ValidationError(
                    'Used physiotherapy sessions cannot be negative.'
                )

            if (
                record.used_physio_sessions
                > record.included_physio_sessions
            ):
                record.used_physio_sessions = (
                    record._origin.used_physio_sessions
                    if record._origin
                    else 0
                )

                raise ValidationError(
                    'Used physiotherapy sessions cannot exceed included '
                    'physiotherapy sessions.'
                )

            if record.used_nutrition_consultations < 0:
                record.used_nutrition_consultations = 0
                raise ValidationError(
                    'Used nutrition consultations cannot be negative.'
                )

            if (
                record.used_nutrition_consultations
                > record.included_nutrition_consultations
            ):
                record.used_nutrition_consultations = (
                    record._origin.used_nutrition_consultations
                    if record._origin
                    else 0
                )

                raise ValidationError(
                    'Used nutrition consultations cannot exceed included '
                    'nutrition consultations.'
                )

    @api.depends('price', 'discount')
    def _compute_final_price(self):
        for record in self:
            record.final_price = max(
                record.price - record.discount,
                0.0,
            )

    @api.depends('allowed_freeze_days', 'used_freeze_days')
    def _compute_remaining_freeze_days(self):
        for record in self:
            record.remaining_freeze_days = max(
                record.allowed_freeze_days - record.used_freeze_days,
                0,
            )

    @api.depends('included_pt_sessions', 'used_pt_sessions')
    def _compute_remaining_pt_sessions(self):
        for record in self:
            record.remaining_pt_sessions = max(
                record.included_pt_sessions - record.used_pt_sessions,
                0,
            )

    @api.depends(
        'package_id',
        'package_id.duration_months',
        'package_id.included_physio_sessions_per_month',
    )
    def _compute_included_physio_sessions(self):
        for record in self:
            record.included_physio_sessions = (
                record.package_id.included_physio_sessions_per_month
                * record.package_id.duration_months
            )

    @api.depends(
        'included_physio_sessions',
        'used_physio_sessions',
    )
    def _compute_remaining_physio_sessions(self):
        for record in self:
            record.remaining_physio_sessions = max(
                record.included_physio_sessions
                - record.used_physio_sessions,
                0,
            )

    @api.depends(
        'included_nutrition_consultations',
        'used_nutrition_consultations',
    )
    def _compute_remaining_nutrition_consultations(self):
        for record in self:
            record.remaining_nutrition_consultations = max(
                record.included_nutrition_consultations
                - record.used_nutrition_consultations,
                0,
            )

    @api.constrains(
        'subscription_date',
        'activation_date',
        'original_expiration_date',
        'expiration_date',
    )
    def _check_dates(self):
        for record in self:

            if (
                record.subscription_date
                and record.activation_date
                and record.activation_date < record.subscription_date
            ):
                raise ValidationError(
                    'Activation date cannot be before subscription date.'
                )

            if (
                record.activation_date
                and record.original_expiration_date
                and record.original_expiration_date < record.activation_date
            ):
                raise ValidationError(
                    'Expiration date cannot be before activation date.'
                )

            if (
                record.activation_date
                and record.expiration_date
                and record.expiration_date < record.activation_date
            ):
                raise ValidationError(
                    'Expiration date cannot be before activation date.'
                )

    @api.constrains(
        'discount',
        'used_freeze_days',
        'used_pt_sessions',
        'used_physio_sessions',
        'used_nutrition_consultations',
    )
    def _check_non_negative_values(self):
        for record in self:

            if record.discount < 0:
                raise ValidationError(
                    'Discount cannot be negative.'
                )

            if record.used_freeze_days < 0:
                raise ValidationError(
                    'Used freeze days cannot be negative.'
                )

            if record.used_pt_sessions < 0:
                raise ValidationError(
                    'Used PT sessions cannot be negative.'
                )

            if record.used_physio_sessions < 0:
                raise ValidationError(
                    'Used physiotherapy sessions cannot be negative.'
                )

            if record.used_nutrition_consultations < 0:
                raise ValidationError(
                    'Used nutrition consultations cannot be negative.'
                )

    @api.constrains(
        'used_freeze_days',
        'allowed_freeze_days',
    )
    def _check_freeze_days(self):
        for record in self:

            if record.used_freeze_days > record.allowed_freeze_days:
                raise ValidationError(
                    'Used freeze days cannot exceed the allowed freeze days.'
                )

    @api.constrains(
        'used_pt_sessions',
        'included_pt_sessions',
        'used_physio_sessions',
        'included_physio_sessions',
        'used_nutrition_consultations',
        'included_nutrition_consultations',
    )
    def _check_used_services(self):
        for record in self:

            if record.used_pt_sessions > record.included_pt_sessions:
                raise ValidationError(
                    'Used PT sessions cannot exceed included PT sessions.'
                )

            if (
                record.used_physio_sessions
                > record.included_physio_sessions
            ):
                raise ValidationError(
                    'Used physiotherapy sessions cannot exceed included '
                    'physiotherapy sessions.'
                )

            if (
                record.used_nutrition_consultations
                > record.included_nutrition_consultations
            ):
                raise ValidationError(
                    'Used nutrition consultations cannot exceed included '
                    'nutrition consultations.'
                )

    @api.model
    def _cron_update_membership_statuses(self):
        today = fields.Date.context_today(self)

        draft_memberships = self.search([
            ('status', '=', 'draft'),
            ('activation_date', '!=', False),
            ('activation_date', '<=', today),
        ])

        draft_memberships.write({
            'status': 'active',
        })

        active_memberships = self.search([
            ('status', '=', 'active'),
            ('expiration_date', '!=', False),
            ('expiration_date', '<', today),
        ])

        active_memberships.write({
            'status': 'expired',
        })

        return True

    
    def action_resume_after_freeze(self):
        for record in self:
            if record.status != 'frozen':
                raise ValidationError(
                    'Only frozen memberships can be resumed.'
                )

            freeze = self.env['fitzone.membership.freeze'].search(
                [
                    ('subscription_id', '=', record.id),
                    ('status', '=', 'active'),
                ],
                order='start_date desc, id desc',
                limit=1,
            )

            if not freeze:
                raise ValidationError(
                    'No active freeze was found for this membership.'
                )

            today = fields.Date.context_today(record)

            if today < freeze.start_date:
                actual_days = 0
            else:
                actual_days = (
                    today - freeze.start_date
                ).days + 1

            actual_days = min(
                actual_days,
                freeze.freeze_days,
            )

            unused_days = freeze.freeze_days - actual_days

            if (
                unused_days > 0
                and record.expiration_date
            ):
                record.expiration_date = (
                    record.expiration_date
                    - relativedelta(days=unused_days)
                )

            freeze.actual_freeze_days = actual_days
            freeze.status = 'completed'

            record.used_freeze_days += actual_days

            if (
                record.expiration_date
                and record.expiration_date < today
            ):
                record.status = 'expired'
            else:
                record.status = 'active'
        return True
