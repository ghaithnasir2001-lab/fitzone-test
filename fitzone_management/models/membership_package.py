from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneMembershipPackage(models.Model):
    _name = 'fitzone.membership.package'
    _description = 'FitZone Membership Package'
    _order = 'package_type, duration_months'

    name = fields.Char(
        string='Package Name',
        required=True,
    )

    package_type = fields.Selection(
        [
            ('general', 'General'),
            ('private', 'Private'),
            ('all_inclusive', 'All-Inclusive'),
        ],
        string='Package Type',
        required=True,
    )

    duration_months = fields.Integer(
        string='Duration (Months)',
        required=True,
    )

    price = fields.Monetary(
        string='Price',
        currency_field='currency_id',
        compute='_compute_price',
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    freeze_days = fields.Integer(
        string='Allowed Freeze Days',
        required=True,
        default=0,
    )

    included_pt_sessions = fields.Integer(
        string='Included PT Sessions',
        default=0,
    )

    included_physio_sessions_per_month = fields.Integer(
        string='Physiotherapy Sessions / Month',
        default=0,
    )

    included_nutrition_consultations = fields.Integer(
        string='Nutrition Consultations',
        default=0,
    )

    description = fields.Text(
        string='Included Services / Description',
    )

    active = fields.Boolean(
        string='Active',
        default=True,
    )

    @api.depends(
        'package_type',
        'duration_months',
        'currency_id',
    )
    def _compute_price(self):
        for record in self:

            fixed_prices = {
                ('general', 1): 50.0,
                ('general', 3): 135.0,
                ('general', 6): 250.0,
                ('private', 1): 150.0,
                ('private', 2): 280.0,
            }

            if record.package_type == 'all_inclusive':
                general_package = self.search([
                    ('package_type', '=', 'general'),
                    ('duration_months', '=', record.duration_months),
                    ('currency_id', '=', record.currency_id.id),
                    ('active', '=', True),
                    ('id', '!=', record.id),
                ], limit=1)

                record.price = (
                    general_package.price + 20.0
                    if general_package
                    else 0.0
                )

            else:
                record.price = fixed_prices.get(
                    (record.package_type, record.duration_months),
                    0.0,
                )

    @api.constrains('duration_months', 'price', 'freeze_days')
    def _check_positive_values(self):
        for record in self:

            if record.duration_months <= 0:
                raise ValidationError(
                    'Package duration must be greater than zero.'
                )

            if record.price < 0:
                raise ValidationError(
                    'Package price cannot be negative.'
                )

            if record.freeze_days < 0:
                raise ValidationError(
                    'Freeze days cannot be negative.'
                )

    @api.constrains(
        'package_type',
        'duration_months',
        'included_pt_sessions',
        'included_physio_sessions_per_month',
        'included_nutrition_consultations',
    )
    def _check_package_rules(self):
        for record in self:

            if record.included_pt_sessions < 0:
                raise ValidationError(
                    'Included PT sessions cannot be negative.'
                )

            if record.included_physio_sessions_per_month < 0:
                raise ValidationError(
                    'Physiotherapy sessions cannot be negative.'
                )

            if record.included_nutrition_consultations < 0:
                raise ValidationError(
                    'Nutrition consultations cannot be negative.'
                )

            if record.package_type == 'general':
                if record.included_pt_sessions:
                    raise ValidationError(
                        'General membership cannot include dedicated PT sessions.'
                    )

            if record.package_type == 'private':
                if record.included_pt_sessions <= 0:
                    raise ValidationError(
                        'Private membership must include PT sessions.'
                    )

            if record.package_type == 'all_inclusive':
                if record.included_physio_sessions_per_month != 2:
                    raise ValidationError(
                        'All-Inclusive membership must include 2 physiotherapy '
                        'sessions per month.'
                    )

                if record.included_nutrition_consultations != 1:
                    raise ValidationError(
                        'All-Inclusive membership must include 1 nutrition '
                        'consultation for the membership duration.'
                    )

                if record.price <= 0:
                    raise ValidationError(
                        'All-Inclusive membership requires an active General '
                        'package with the same duration.'
                    )

    @api.onchange('package_type', 'duration_months')
    def _onchange_package_rules(self):
        for record in self:

            if not record.duration_months:
                continue

            # Freeze rules
            if record.duration_months == 1:
                record.freeze_days = 7
            elif record.duration_months == 2:
                record.freeze_days = 14
            elif record.duration_months == 3:
                record.freeze_days = 14
            elif record.duration_months >= 6:
                record.freeze_days = 30
            else:
                record.freeze_days = 0

            # Private membership PT sessions
            if record.package_type == 'private':
                if record.duration_months == 1:
                    record.included_pt_sessions = 12
                elif record.duration_months == 2:
                    record.included_pt_sessions = 24
                else:
                    record.included_pt_sessions = 0

            else:
                record.included_pt_sessions = 0

            # All-Inclusive services
            if record.package_type == 'all_inclusive':
                record.included_physio_sessions_per_month = 2
                record.included_nutrition_consultations = 1
            else:
                record.included_physio_sessions_per_month = 0
                record.included_nutrition_consultations = 0