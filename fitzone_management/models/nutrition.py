from odoo import api, fields, models
from odoo.exceptions import ValidationError


def _get_nutrition_consultation_price(env):
    value = env['ir.config_parameter'].sudo().get_param(
        'fitzone_management.nutrition_consultation_price',
        '0.0',
    )
    return float(value or 0.0)


class FitZoneNutritionProgram(models.Model):
    _name = 'fitzone.nutrition.program'
    _description = 'FitZone Nutrition Program'
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string='Program Name',
        required=True,
    )

    subscriber_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        required=True,
        domain=[('is_fitzone_subscriber', '=', True)],
        ondelete='restrict',
    )

    nutritionist_id = fields.Many2one(
        'hr.employee',
        string='Nutritionist',
        required=True,
        domain=[('fitzone_staff_type', '=', 'nutritionist')],
        ondelete='restrict',
    )

    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
    )

    end_date = fields.Date(
        string='End Date',
    )

    status = fields.Selection(
        [
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='active',
    )

    goals = fields.Text(string='Goals')
    notes = fields.Text(string='Notes')

    consultation_ids = fields.One2many(
        'fitzone.nutrition.consultation',
        'program_id',
        string='Consultations',
    )

    @api.constrains('subscriber_id')
    def _check_subscriber(self):
        for record in self:
            if (
                record.subscriber_id
                and not record.subscriber_id.is_fitzone_subscriber
            ):
                raise ValidationError(
                    'A nutrition program can only be created '
                    'for a FitZone subscriber.'
                )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if (
                record.start_date
                and record.end_date
                and record.end_date < record.start_date
            ):
                raise ValidationError(
                    'End Date cannot be earlier than Start Date.'
                )


class FitZoneNutritionConsultation(models.Model):
    _name = 'fitzone.nutrition.consultation'
    _description = 'FitZone Nutrition Consultation'
    _order = 'consultation_date desc, id desc'

    name = fields.Char(
        string='Consultation Reference',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: (
            self.env['ir.sequence'].next_by_code(
                'fitzone.nutrition.consultation'
            ) or 'New'
        ),
    )

    subscriber_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        required=True,
        domain=[('is_fitzone_subscriber', '=', True)],
        ondelete='restrict',
    )

    program_id = fields.Many2one(
        'fitzone.nutrition.program',
        string='Nutrition Program',
        domain="[('subscriber_id', '=', subscriber_id)]",
        ondelete='restrict',
    )

    subscription_id = fields.Many2one(
        'fitzone.membership.subscription',
        string='Membership Subscription',
        domain="[('subscriber_id', '=', subscriber_id)]",
        ondelete='restrict',
        help='Membership used for the included nutrition consultation.',
    )

    uses_included_consultation = fields.Boolean(
        string='Uses Included Consultation',
        default=False,
        help=(
            'Enable this when this consultation uses the nutrition '
            'consultation included in an All-Inclusive membership.'
        ),
    )

    nutritionist_id = fields.Many2one(
        'hr.employee',
        string='Nutritionist',
        required=True,
        domain=[('fitzone_staff_type', '=', 'nutritionist')],
        ondelete='restrict',
    )

    consultation_date = fields.Date(
        string='Consultation Date',
        required=True,
        default=fields.Date.context_today,
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

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    consultation_price = fields.Monetary(
        string='Consultation Price',
        currency_field='currency_id',
        default=lambda self: _get_nutrition_consultation_price(self.env),
        copy=False,
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Consultation Invoice',
        readonly=True,
        copy=False,
        ondelete='restrict',
    )

    invoice_payment_state = fields.Selection(
        related='invoice_id.payment_state',
        string='Payment Status',
        readonly=True,
    )

    notes = fields.Text(string='Consultation Notes')
    recommendations = fields.Text(string='Recommendations')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            program_id = vals.get('program_id')
            subscription_id = vals.get('subscription_id')
            uses_included = vals.get('uses_included_consultation', False)

            if program_id and not vals.get('subscriber_id'):
                program = self.env[
                    'fitzone.nutrition.program'
                ].browse(program_id).exists()

                if program:
                    vals['subscriber_id'] = program.subscriber_id.id

            if subscription_id and not vals.get('subscriber_id'):
                subscription = self.env[
                    'fitzone.membership.subscription'
                ].browse(subscription_id).exists()

                if subscription:
                    vals['subscriber_id'] = subscription.subscriber_id.id

            # Included consultations are free.
            if uses_included:
                vals['consultation_price'] = 0.0
            elif 'consultation_price' not in vals:
                vals['consultation_price'] = (
                    _get_nutrition_consultation_price(self.env)
                )

        return super().create(vals_list)

    def write(self, vals):
        vals = vals.copy()

        if (
            'state' in vals
            and not self.env.context.get(
                '_allow_nutrition_state_transition'
            )
        ):
            raise ValidationError(
                'Change consultation status using the available actions.'
            )

        # Keep the price consistent when changing between included
        # and paid consultations, provided no invoice exists yet.
        if 'uses_included_consultation' in vals:
            for record in self:
                if record.invoice_id:
                    raise ValidationError(
                        'You cannot change the consultation benefit '
                        'after an invoice has been created.'
                    )

            if vals['uses_included_consultation']:
                vals['consultation_price'] = 0.0
            elif 'consultation_price' not in vals:
                vals['consultation_price'] = (
                    _get_nutrition_consultation_price(self.env)
                )

        if 'consultation_price' in vals:
            for record in self:
                if record.invoice_id:
                    raise ValidationError(
                        'You cannot change the price after an invoice '
                        'has been created.'
                    )

            if vals['consultation_price'] < 0:
                raise ValidationError(
                    'Consultation price cannot be negative.'
                )

        return super().write(vals)

    @api.constrains('subscriber_id')
    def _check_subscriber(self):
        for record in self:
            if (
                record.subscriber_id
                and not record.subscriber_id.is_fitzone_subscriber
            ):
                raise ValidationError(
                    'A nutrition consultation can only be created '
                    'for a FitZone subscriber.'
                )

    @api.constrains('program_id', 'subscriber_id')
    def _check_program_subscriber(self):
        for record in self:
            if (
                record.program_id
                and record.subscriber_id
                and record.program_id.subscriber_id
                != record.subscriber_id
            ):
                raise ValidationError(
                    'The consultation subscriber must match '
                    'the nutrition program subscriber.'
                )

    @api.constrains('subscription_id', 'subscriber_id')
    def _check_subscription_subscriber(self):
        for record in self:
            if (
                record.subscription_id
                and record.subscriber_id
                and record.subscription_id.subscriber_id
                != record.subscriber_id
            ):
                raise ValidationError(
                    'The membership subscriber must match '
                    'the consultation subscriber.'
                )

    @api.constrains(
        'uses_included_consultation',
        'subscription_id',
        'subscriber_id',
        'consultation_date',
    )
    def _check_included_consultation(self):
        for record in self:
            if not record.uses_included_consultation:
                continue

            subscription = record.subscription_id

            if not subscription:
                raise ValidationError(
                    'Select a membership subscription to use '
                    'the included consultation.'
                )

            if subscription.subscriber_id != record.subscriber_id:
                raise ValidationError(
                    'The selected membership belongs to another subscriber.'
                )

            package = subscription.package_id

            if not (
                package.is_all_inclusive
                or package.package_type == 'all_inclusive'
            ):
                raise ValidationError(
                    'The included nutrition consultation is only available '
                    'with an All-Inclusive membership.'
                )

            if subscription.status != 'active':
                raise ValidationError(
                    'The membership must be active to use '
                    'the included consultation.'
                )

            if (
                subscription.activation_date
                and record.consultation_date < subscription.activation_date
            ):
                raise ValidationError(
                    'The consultation date cannot be before '
                    'the membership activation date.'
                )

            if (
                subscription.expiration_date
                and record.consultation_date > subscription.expiration_date
            ):
                raise ValidationError(
                    'The consultation date must be within '
                    'the membership period.'
                )

            already_used = self.search_count([
                ('subscription_id', '=', subscription.id),
                ('uses_included_consultation', '=', True),
                ('state', 'in', ['scheduled', 'completed']),
                ('id', '!=', record.id),
            ])

            if (
                already_used
                >= subscription.included_nutrition_consultations
            ):
                raise ValidationError(
                    'No included nutrition consultations remain '
                    'for this membership.'
                )

    def action_mark_completed(self):
        for record in self:
            if record.state == 'cancelled':
                raise ValidationError(
                    'A cancelled consultation cannot be completed.'
                )
            if record.state == 'completed':
                continue
            if record.uses_included_consultation:
                record._check_included_consultation()
            record.with_context(
                _allow_nutrition_state_transition=True
            ).write({'state': 'completed'})
        return True

    def action_cancel(self):
        for record in self:
            if record.state == 'completed':
                raise ValidationError(
                    'A completed consultation cannot be cancelled.'
                )
            if record.state != 'cancelled':
                record.with_context(
                    _allow_nutrition_state_transition=True
                ).write({'state': 'cancelled'})
        return True

    def action_create_invoice(self):
        self.ensure_one()

        if self.uses_included_consultation:
            raise ValidationError(
                'Included consultations do not require an invoice.'
            )

        if self.invoice_id:
            raise ValidationError(
                'An invoice already exists for this consultation.'
            )

        if self.consultation_price <= 0:
            raise ValidationError(
                'Configure a consultation price greater than zero first.'
            )

        company = self.env.company

        income_account = self.env['account.account'].search([
            ('account_type', 'in', ['income', 'income_other']),
            ('company_ids', 'in', [company.id]),
        ], limit=1)

        if not income_account:
            raise ValidationError(
                'No income account is configured for this company.'
            )

        tax = self.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 16),
            ('active', '=', True),
            ('company_id', '=', company.id),
        ], limit=1)

        if not tax:
            raise ValidationError(
                'The active 16% sales tax was not found for this company.'
            )

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.subscriber_id.id,
            'company_id': company.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': [
                fields.Command.create({
                    'name': f'{self.name} - Nutrition Consultation',
                    'quantity': 1.0,
                    # Consultation price is inclusive of 16% tax.
                    'price_unit': self.consultation_price / 1.16,
                    'account_id': income_account.id,
                    'tax_ids': [
                        fields.Command.set([tax.id])
                    ],
                }),
            ],
        })

        invoice.action_post()
        self.invoice_id = invoice.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Consultation Invoice',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ResPartner(models.Model):
    _inherit = 'res.partner'

    nutrition_program_ids = fields.One2many(
        'fitzone.nutrition.program',
        'subscriber_id',
        string='Nutrition Programs',
    )

    nutrition_consultation_ids = fields.One2many(
        'fitzone.nutrition.consultation',
        'subscriber_id',
        string='Nutrition Consultations',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    nutrition_consultation_price = fields.Float(
        string='Nutrition Consultation Price (JOD)',
        config_parameter=(
            'fitzone_management.nutrition_consultation_price'
        ),
        default=0.0,
    )
