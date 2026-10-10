from datetime import datetime, time
import base64

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class FitZoneMembershipSubscription(models.Model):
    _name = 'fitzone.membership.subscription'
    _description = 'FitZone Membership Subscription'
    _order = 'subscription_date desc, id desc'

    _barcode_unique = models.Constraint(
        'UNIQUE(barcode)',
        'Membership barcode must be unique.',
    )

    name = fields.Char(
        string='Membership Number',
        required=True,
        copy=False,
        default='New',
    )

    barcode = fields.Char(
        string='Barcode',
        copy=False,
        readonly=True,
        index=True,
    )

    subscriber_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        ondelete='restrict',
    )

    package_id = fields.Many2one(
        'fitzone.membership.package',
        string='Membership Package',
        required=True,
        ondelete='restrict',
    )

    subscription_date = fields.Date(
        string='Subscription Date',
        required=True,
        default=fields.Date.context_today,
    )

    activation_date = fields.Date(
        string='Activation Date',
        required=True,
        default=fields.Date.context_today,
    )

    original_expiration_date = fields.Date(
        string='Original Expiration Date',
        readonly=True,
        copy=False,
    )

    expiration_date = fields.Date(
        string='Expiration Date',
        readonly=True,
        copy=False,
    )

    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('frozen', 'Frozen'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled'),
            ('renewed', 'Renewed'),
        ],
        string='Status',
        required=True,
        default='draft',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='package_id.currency_id',
        store=True,
        readonly=True,
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

    payment_plan = fields.Selection(
        [
            ('full', 'Full Payment'),
            ('installments', 'Two Installments'),
        ],
        string='Payment Plan',
        required=True,
        default='full',
    )

    first_installment_amount = fields.Monetary(
        string='First Installment Amount',
        currency_field='currency_id',
    )

    second_installment_due_date = fields.Date(
        string='Second Installment Due Date',
    )

    second_installment_amount = fields.Monetary(
        string='Second Installment Amount',
        currency_field='currency_id',
        compute='_compute_second_installment_amount',
    )

    installment_ids = fields.One2many(
        'fitzone.membership.installment',
        'subscription_id',
        string='Installments',
        copy=False,
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Full Membership Invoice',
        readonly=True,
        copy=False,
        ondelete='restrict',
    )

    payment_access_blocked = fields.Boolean(
        string='Access Blocked Due to Overdue Payment',
        compute='_compute_payment_access_blocked',
    )

    @api.depends('final_price', 'first_installment_amount')
    def _compute_second_installment_amount(self):
        for record in self:
            record.second_installment_amount = max(
                record.final_price - record.first_installment_amount,
                0.0,
            )

    @api.depends(
        'payment_plan',
        'installment_ids.payment_status',
        'installment_ids.installment_number',
        'installment_ids.due_date',
        'installment_ids.invoice_id.amount_residual',
    )
    def _compute_payment_access_blocked(self):
        for record in self:
            record.payment_access_blocked = any(
                line.installment_number == '2'
                and line.payment_status == 'overdue'
                for line in record.installment_ids
            )

    allowed_freeze_days = fields.Integer(
        string='Allowed Freeze Days',
        related='package_id.freeze_days',
        store=True,
        readonly=True,
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
        readonly=True,
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
        string='Used Physiotherapy Sessions This Month',
        compute='_compute_used_physio_sessions',
        readonly=True,
    )

    remaining_physio_sessions = fields.Integer(
        string='Remaining Physiotherapy Sessions This Month',
        compute='_compute_remaining_physio_sessions',
        readonly=True,
    )

    included_nutrition_consultations = fields.Integer(
        string='Included Nutrition Consultations',
        related='package_id.included_nutrition_consultations',
        store=True,
        readonly=True,
    )

    nutrition_consultation_ids = fields.One2many(
        'fitzone.nutrition.consultation',
        'subscription_id',
        string='Nutrition Consultations',
    )

    used_nutrition_consultations = fields.Integer(
        string='Used Nutrition Consultations',
        compute='_compute_used_nutrition_consultations',
        store=True,
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
        copy=False,
    )

    notes = fields.Text(
        string='Notes',
    )

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:
            if not vals.get('subscriber_id'):
                raise ValidationError("Please select a subscriber before creating a membership subscription.")
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'fitzone.membership.subscription'
                ) or 'New'

            if not vals.get('barcode'):
                vals['barcode'] = self.env['ir.sequence'].next_by_code(
                    'fitzone.membership.barcode'
                ) or False

            package = self.env[
                'fitzone.membership.package'
            ].browse(
                vals.get('package_id')
            )

            if package.exists():

                if not vals.get('price'):
                    vals['price'] = package.price

                subscription_date = vals.get(
                    'subscription_date'
                ) or fields.Date.context_today(self)

                activation_date = vals.get(
                    'activation_date'
                ) or subscription_date

                subscription_date = fields.Date.to_date(
                    subscription_date
                )

                activation_date = fields.Date.to_date(
                    activation_date
                )

                if activation_date < subscription_date:
                    raise ValidationError(
                        'Activation date cannot be before subscription date.'
                    )

                vals['subscription_date'] = subscription_date
                vals['activation_date'] = activation_date

                expiration_date = (
                    activation_date
                    + relativedelta(
                        months=package.duration_months
                    )
                    - relativedelta(days=1)
                )

                vals['original_expiration_date'] = expiration_date
                vals['expiration_date'] = expiration_date

                today = fields.Date.context_today(self)

                if activation_date <= today:
                    vals['status'] = 'active'
                else:
                    vals['status'] = 'draft'

        return super().create(vals_list)

    def write(self, vals):

        result = super().write(vals)

        if (
            'activation_date' in vals
            or 'expiration_date' in vals
        ):
            today = fields.Date.context_today(self)

            for record in self:

                if record.status in (
                    'cancelled',
                    'renewed',
                    'frozen',
                ):
                    continue

                if (
                    record.activation_date
                    and record.activation_date > today
                ):
                    record.status = 'draft'

                elif (
                    record.expiration_date
                    and record.expiration_date < today
                ):
                    record.status = 'expired'

                else:
                    record.status = 'active'

        if 'second_installment_due_date' in vals:
            for subscription in self:
                due_date = subscription.second_installment_due_date

                if not due_date:
                    continue

                second_installment = self.env[
                    'fitzone.membership.installment'
                ].search([
                    ('subscription_id', '=', subscription.id),
                    ('installment_number', '=', '2'),
                ], limit=1)

                if (
                    second_installment
                    and second_installment.due_date != due_date
                ):
                    second_installment.write({
                        'due_date': due_date,
                    })

        return result

    def action_create_payment_plan(self):
        for subscription in self:
            if subscription.payment_plan != 'installments':
                raise UserError(
                    'Select the two-installment payment plan first.'
                )

            if subscription.installment_ids:
                raise UserError(
                    'A payment plan already exists for this membership.'
                )

            if subscription.invoice_id:
                raise UserError(
                    'A full membership invoice already exists.'
                )

            duration = subscription.package_id.duration_months

            if duration < 3:
                raise ValidationError(
                    'Installments are allowed only for memberships '
                    'of three months or longer.'
                )

            package = subscription.package_id

            monthly_domain = [
                ('duration_months', '=', 1),
                ('currency_id', '=', package.currency_id.id),
                ('active', '=', True),
            ]

            if package.is_all_inclusive or package.package_type == 'all_inclusive':
                monthly_domain += [
                    '|',
                    ('is_all_inclusive', '=', True),
                    ('package_type', '=', 'all_inclusive'),
                ]
            elif package.package_type == 'private':
                monthly_domain += [
                    ('package_type', '=', 'private'),
                    ('is_all_inclusive', '=', False),
                ]
            else:
                monthly_domain += [
                    ('package_type', '=', 'general'),
                    ('is_all_inclusive', '=', False),
                ]

            monthly_package = self.env[
                'fitzone.membership.package'
            ].search(
                monthly_domain,
                limit=1,
            )

            if not monthly_package:
                raise UserError(
                    'Create an active one-month package of the same type '
                    'before creating the installment plan.'
                )

            minimum_first_amount = monthly_package.price

            first_amount = subscription.first_installment_amount
            second_amount = (
                subscription.final_price - first_amount
            )

            if first_amount < minimum_first_amount:
                raise ValidationError(
                    'The first installment must be at least the price '
                    'of a one-month package of the same type: '
                    f'{minimum_first_amount:.2f}.'
                )

            if first_amount <= 0 or second_amount <= 0:
                raise ValidationError(
                    'Both installments must have a positive amount.'
                )

            if not subscription.second_installment_due_date:
                raise ValidationError(
                    'Set the second installment due date first.'
                )

            if (
                subscription.second_installment_due_date
                < subscription.subscription_date
            ):
                raise ValidationError(
                    'The second installment due date cannot be before '
                    'the subscription date.'
                )

            self.env['fitzone.membership.installment'].create([
                {
                    'subscription_id': subscription.id,
                    'installment_number': '1',
                    'amount': first_amount,
                    'due_date': subscription.subscription_date,
                },
                {
                    'subscription_id': subscription.id,
                    'installment_number': '2',
                    'amount': second_amount,
                    'due_date': subscription.second_installment_due_date,
                },
            ])

        return True

    def action_create_full_invoice(self):
        for subscription in self:
            if subscription.payment_plan != 'full':
                raise UserError(
                    'This membership uses installments. '
                    'Create invoices from its installment records.'
                )

            if subscription.invoice_id:
                raise UserError(
                    'A full membership invoice already exists.'
                )

            company = self.env.company

            income_account = self.env['account.account'].search([
                ('company_ids', 'in', [company.id]),
                ('account_type', 'in', ['income', 'income_other']),
            ], limit=1)

            if not income_account:
                raise UserError(
                    'Configure an income account in Odoo Accounting first.'
                )

            tax = self.env['account.tax'].search([
                ('company_id', '=', company.id),
                ('type_tax_use', '=', 'sale'),
                ('amount', '=', 16.0),
                ('active', '=', True),
            ], limit=1)

            if not tax:
                raise UserError(
                    'Configure the 16% sales tax in Odoo Accounting first'
                )

            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': subscription.subscriber_id.id,
                'company_id': company.id,
                'invoice_date': fields.Date.context_today(subscription),
                'invoice_line_ids': [
                    fields.Command.create({
                        'name': (
                            f'{subscription.name} - Membership'
                        ),
                        'quantity': 1.0,
                        'price_unit': subscription.final_price / 1.16,
                        'account_id': income_account.id,
                        'tax_ids': [fields.Command.set([tax.id])],
                    }),
                ],
            })

            invoice.action_post()
            subscription.invoice_id = invoice.id
        return True

    @api.onchange(
        'subscription_date',
        'activation_date',
        'package_id',
    )
    def _onchange_subscription_dates(self):

        for record in self:

            if record.subscription_date:
                if not record.activation_date:
                    record.activation_date = record.subscription_date

                elif record.activation_date < record.subscription_date:
                    record.activation_date = record.subscription_date

            if record.package_id:

                record.price = record.package_id.price

                if record.activation_date:

                    record.expiration_date = (
                        record.activation_date
                        + relativedelta(
                            months=record.package_id.duration_months
                        )
                        - relativedelta(days=1)
                    )

    @api.onchange(
        'discount',
        'used_freeze_days',
        'used_pt_sessions',
        'used_nutrition_consultations',
    )
    def _onchange_non_negative_values(self):

        for record in self:

            if record.discount < 0:
                record.discount = 0

            if record.used_freeze_days < 0:
                record.used_freeze_days = 0

            if record.used_pt_sessions < 0:
                record.used_pt_sessions = 0

            if record.used_nutrition_consultations < 0:
                record.used_nutrition_consultations = 0

            if record.used_physio_sessions < 0:
                record.used_physio_sessions = 0

    @api.depends('price', 'discount')
    def _compute_final_price(self):

        for record in self:

            record.final_price = max(
                record.price - record.discount,
                0.0,
            )

    @api.depends(
        'allowed_freeze_days',
        'used_freeze_days',
    )
    def _compute_remaining_freeze_days(self):

        for record in self:

            record.remaining_freeze_days = max(
                record.allowed_freeze_days
                - record.used_freeze_days,
                0,
            )

    @api.depends(
        'included_pt_sessions',
        'used_pt_sessions',
    )
    def _compute_remaining_pt_sessions(self):

        for record in self:

            record.remaining_pt_sessions = max(
                record.included_pt_sessions
                - record.used_pt_sessions,
                0,
            )

    @api.depends(
        'package_id',
        'package_id.included_physio_sessions_per_month',
    )
    def _compute_included_physio_sessions(self):

        for record in self:
            record.included_physio_sessions = (
                record.package_id.included_physio_sessions_per_month
                if record.package_id
                else 0
            )

    def _get_physio_period(self, usage_date):
        self.ensure_one()

        if not self.activation_date or not self.expiration_date:
            return False, False

        usage_date = fields.Date.to_date(usage_date)
        activation_date = fields.Date.to_date(
            self.activation_date
        )
        expiration_date = fields.Date.to_date(
            self.expiration_date
        )

        if usage_date < activation_date or usage_date > expiration_date:
            return False, False

        months_elapsed = (
            (usage_date.year - activation_date.year) * 12
            + usage_date.month
            - activation_date.month
        )

        period_start = (
            activation_date
            + relativedelta(months=months_elapsed)
        )

        period_end = (
            period_start
            + relativedelta(months=1)
            - relativedelta(days=1)
        )

        if period_end > expiration_date:
            period_end = expiration_date

        return period_start, period_end

    def _count_completed_physio_treatments(
        self,
        period_start,
        period_end,
    ):
        self.ensure_one()

        if not period_start or not period_end:
            return 0

        start_datetime = datetime.combine(
            period_start,
            time.min,
        )

        end_datetime = datetime.combine(
            period_end,
            time.max,
        )

        return self.env['fitzone.treatment'].sudo().search_count(
            [
                (
                    'rehab_file_id.partner_id',
                    '=',
                    self.subscriber_id.id,
                ),
                (
                    'state',
                    '=',
                    'completed',
                ),
                (
                    'booking_id.booking_type',
                    '=',
                    'physiotherapy',
                ),
                (
                    'booking_id.start_datetime',
                    '>=',
                    start_datetime,
                ),
                (
                    'booking_id.start_datetime',
                    '<=',
                    end_datetime,
                ),
            ]
        )

    @api.depends(
        'subscriber_id',
        'package_id',
        'activation_date',
        'expiration_date',
        'status',
    )
    def _compute_used_physio_sessions(self):

        for record in self:

            today = fields.Date.context_today(record)

            if (
                not record.subscriber_id
                or record.status == 'cancelled'
            ):
                record.used_physio_sessions = 0
                continue

            period_start, period_end = record._get_physio_period(
                today
            )

            if not period_start or not period_end:
                record.used_physio_sessions = 0
                continue

            record.used_physio_sessions = (
                record._count_completed_physio_treatments(
                    period_start,
                    period_end,
                )
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
        'nutrition_consultation_ids',
        'nutrition_consultation_ids.uses_included_consultation',
    )
    def _compute_used_nutrition_consultations(self):
        for record in self:
            record.used_nutrition_consultations = sum(
                1
                for consultation in record.nutrition_consultation_ids
                if consultation.uses_included_consultation
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
        'expiration_date',
    )
    def _check_membership_dates(self):

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

            if record.used_nutrition_consultations < 0:
                raise ValidationError(
                    'Used nutrition consultations cannot be negative.'
                )

    @api.constrains(
        'used_freeze_days',
        'allowed_freeze_days',
    )
    def _check_used_freeze_days(self):

        for record in self:

            if record.used_freeze_days > record.allowed_freeze_days:
                raise ValidationError(
                    'Used freeze days cannot exceed the allowed freeze days.'
                )

    @api.constrains(
        'used_pt_sessions',
        'included_pt_sessions',
    )
    def _check_used_pt_sessions(self):

        for record in self:

            if record.used_pt_sessions > record.included_pt_sessions:
                raise ValidationError(
                    'Used PT sessions cannot exceed included PT sessions.'
                )

    @api.constrains(
        'used_nutrition_consultations',
        'included_nutrition_consultations',
    )
    def _check_used_nutrition_consultations(self):

        for record in self:

            if (
                record.used_nutrition_consultations
                > record.included_nutrition_consultations
            ):
                raise ValidationError(
                    'Used nutrition consultations cannot exceed '
                    'included nutrition consultations.'
                )

    def _process_attachments_for_template_post(self, mail_template):

        barcode_template = self.env.ref(
            'fitzone_management.email_template_fitzone_membership_barcode'
        )

        if mail_template.id != barcode_template.id:
            return {}

        report = self.env['ir.actions.report']
        result = {}

        for membership in self:

            if not membership.barcode:
                continue

            barcode_image = report.barcode(
                'Code128',
                membership.barcode,
                width=600,
                height=120,
            )

            result[membership.id] = {
                'attachments': [
                    (
                        f'__fitzone_inline_barcode__{membership.id}.png',
                        base64.b64encode(barcode_image),
                    )
                ]
            }

        return result

    def action_send_barcode_email(self):

        template = self.env.ref(
            'fitzone_management.email_template_fitzone_membership_barcode'
        )

        for membership in self:

            if not membership.subscriber_id.email:
                raise ValidationError(
                    'The subscriber does not have an email address.'
                )

            template.send_mail(
                membership.id,
                force_send=True,
            )

        return True

    @api.model
    def verify_barcode(self, barcode):

        barcode = (barcode or '').strip()

        if not barcode:
            return {
                'allowed': False,
                'reason': 'Barcode is required.',
                'membership': False,
            }

        membership = self.search(
            [('barcode', '=', barcode)],
            limit=1,
        )

        if not membership:
            return {
                'allowed': False,
                'reason': 'No membership found for this barcode.',
                'membership': False,
            }

        if membership.status == 'draft':
            return {
                'allowed': False,
                'reason': 'Membership is not active yet.',
                'membership': membership,
            }

        if membership.status == 'frozen':
            return {
                'allowed': False,
                'reason': 'Membership is frozen.',
                'membership': membership,
            }

        if membership.status == 'expired':
            return {
                'allowed': False,
                'reason': 'Membership has expired.',
                'membership': membership,
            }

        if membership.status == 'cancelled':
            return {
                'allowed': False,
                'reason': 'Membership has been cancelled.',
                'membership': membership,
            }

        if membership.status == 'renewed':
            return {
                'allowed': False,
                'reason': 'Membership has been renewed.',
                'membership': membership,
            }

        if membership.status != 'active':
            return {
                'allowed': False,
                'reason': 'Membership is not active.',
                'membership': membership,
            }

        today = fields.Date.context_today(self)

        if membership.expiration_date and membership.expiration_date < today:
            membership.status = 'expired'
            return {
                'allowed': False,
                'reason': 'Membership has expired.',
                'membership': membership,
            }

        active_freeze = self.env[
            'fitzone.membership.freeze'
        ].search(
            [
                ('subscription_id', '=', membership.id),
                ('status', '=', 'active'),
                ('start_date', '<=', today),
                ('end_date', '>=', today),
            ],
            limit=1,
        )

        if active_freeze:
            return {
                'allowed': False,
                'reason': 'Membership is frozen.',
                'membership': membership,
            }

        overdue_second_installment = membership.installment_ids.filtered(
            lambda installment: (
                installment.installment_number == '2'
                and installment.due_date
                and installment.due_date < today
                and (
                    not installment.invoice_id
                    or installment.invoice_id.state != 'posted'
                    or installment.invoice_id.amount_residual > 0.01
                )
            )
        )

        if overdue_second_installment:
            return {
                'allowed': False,
                'reason': 'Second installment is overdue. Check-in is not allowed.',
                'membership': membership,
            }

        return {
            'allowed': True,
            'reason': 'Membership is active.',
            'membership': membership,
        }

    @api.model
    def _cron_update_membership_statuses(self):

        today = fields.Date.context_today(self)

        draft_memberships = self.search(
            [
                ('status', '=', 'draft'),
                ('activation_date', '<=', today),
            ]
        )

        for membership in draft_memberships:
            membership.status = 'active'

        active_memberships = self.search(
            [
                ('status', '=', 'active'),
                ('expiration_date', '<', today),
            ]
        )

        for membership in active_memberships:
            membership.status = 'expired'

    def action_resume_after_freeze(self):

        for subscription in self:

            if subscription.status != 'frozen':
                raise ValidationError(
                    'Only frozen memberships can be resumed.'
                )

            freeze = self.env[
                'fitzone.membership.freeze'
            ].search(
                [
                    ('subscription_id', '=', subscription.id),
                    ('status', '=', 'active'),
                ],
                order='start_date desc, id desc',
                limit=1,
            )

            if not freeze:
                raise ValidationError(
                    'No active freeze was found for this membership.'
                )

            today = fields.Date.context_today(subscription)

            if today < freeze.start_date:
                actual_days = 0
            else:
                actual_days = (
                    today - freeze.start_date
                ).days + 1

            actual_days = min(
                actual_days,
                freeze.applied_freeze_days,
            )

            unused_days = max(
                freeze.applied_freeze_days - actual_days,
                0,
            )

            if unused_days:
                subscription.expiration_date = (
                    subscription.expiration_date
                    - relativedelta(days=unused_days)
                )

            freeze.actual_freeze_days = actual_days
            freeze.status = 'completed'

            subscription.used_freeze_days += actual_days

            if (
                subscription.expiration_date
                and subscription.expiration_date < today
            ):
                subscription.status = 'expired'
            else:
                subscription.status = 'active'

        return True