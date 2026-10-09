
from odoo import api, fields, models
from odoo.exceptions import ValidationError


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

    goals = fields.Text(
        string='Goals',
    )

    notes = fields.Text(
        string='Notes',
    )

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
                    'A nutrition program can only be created for a FitZone subscriber.'
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

    notes = fields.Text(
        string='Consultation Notes',
    )

    recommendations = fields.Text(
        string='Recommendations',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            program_id = vals.get('program_id')
            subscription_id = vals.get('subscription_id')

            # Derive the subscriber from the selected program.
            if program_id and not vals.get('subscriber_id'):
                program = self.env[
                    'fitzone.nutrition.program'
                ].browse(program_id).exists()

                if program:
                    vals['subscriber_id'] = program.subscriber_id.id

            # If a subscription is selected, derive its subscriber too.
            if subscription_id and not vals.get('subscriber_id'):
                subscription = self.env[
                    'fitzone.membership.subscription'
                ].browse(subscription_id).exists()

                if subscription:
                    vals['subscriber_id'] = subscription.subscriber_id.id

        return super().create(vals_list)

    @api.constrains('subscriber_id')
    def _check_subscriber(self):
        for record in self:
            if (
                record.subscriber_id
                and not record.subscriber_id.is_fitzone_subscriber
            ):
                raise ValidationError(
                    'A nutrition consultation can only be created for a FitZone subscriber.'
                )

    @api.constrains('program_id', 'subscriber_id')
    def _check_program_subscriber(self):
        for record in self:
            if (
                record.program_id
                and record.subscriber_id
                and record.program_id.subscriber_id != record.subscriber_id
            ):
                raise ValidationError(
                    'The consultation subscriber must match the nutrition program subscriber.'
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
                    'The membership subscriber must match the consultation subscriber.'
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
                    'Select a membership subscription to use the included consultation.'
                )

            if subscription.subscriber_id != record.subscriber_id:
                raise ValidationError(
                    'The selected membership belongs to another subscriber.'
                )

            # Support both ways of identifying an All-Inclusive package.
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
                    'The membership must be active to use the included consultation.'
                )

            if (
                subscription.activation_date
                and record.consultation_date < subscription.activation_date
            ):
                raise ValidationError(
                    'The consultation date cannot be before the membership activation date.'
                )

            if (
                subscription.expiration_date
                and record.consultation_date > subscription.expiration_date
            ):
                raise ValidationError(
                    'The consultation date must be within the membership period.'
                )

            # Exclude this record so edits to an existing consultation
            # do not count it twice.
            already_used = self.search_count([
                ('subscription_id', '=', subscription.id),
                ('uses_included_consultation', '=', True),
                ('id', '!=', record.id),
            ])

            if (
                already_used
                >= subscription.included_nutrition_consultations
            ):
                raise ValidationError(
                    'No included nutrition consultations remain for this membership.'
                )


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