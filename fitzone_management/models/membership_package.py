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


    is_all_inclusive = fields.Boolean(
        string='All-Inclusive Package',
        default=False,
    )

    duration_months = fields.Integer(
        string='Duration (Months)',
        required=True,
    )

    price = fields.Monetary(
        string='Price',
        currency_field='currency_id',
        required=True,
        default=0.0,
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


    def _get_suggested_price(
        self,
        package_type,
        duration_months,
        currency_id,
        is_all_inclusive=False,
    ):
        """Return the default FitZone package price.

        The returned value is only a suggested/default price.
        The Price field remains editable by the user.
        """

        fixed_prices = {
            ('general', 1): 50.0,
            ('general', 3): 135.0,
            ('general', 6): 250.0,
            ('private', 1): 150.0,
            ('private', 2): 280.0,
        }

        if is_all_inclusive or package_type == 'all_inclusive':
            general_package = self.search(
                [
                    ('package_type', '=', 'general'),
                    ('is_all_inclusive', '=', False),
                    ('duration_months', '=', duration_months),
                    ('currency_id', '=', currency_id),
                    ('active', '=', True),
                ],
                limit=1,
            )

            if general_package:
                return general_package.price + 20.0

            return 0.0

        return fixed_prices.get(
            (package_type, duration_months),
            0.0,
        )


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:

            package_type = vals.get('package_type')
            duration_months = vals.get('duration_months')
            currency_id = vals.get('currency_id') or self.env.company.currency_id.id
            is_all_inclusive = vals.get('is_all_inclusive', False)


            if is_all_inclusive:
                vals['package_type'] = 'general'
                package_type = 'general'

            if not vals.get('price'):
                vals['price'] = self._get_suggested_price(
                    package_type,
                    duration_months,
                    currency_id,
                    is_all_inclusive,
                )

        return super().create(vals_list)



    @api.onchange(
        'package_type',
        'duration_months',
        'currency_id',
        'is_all_inclusive',
    )
    def _onchange_package_defaults(self):
        for record in self:

            if not record.duration_months:
                continue

            if record.is_all_inclusive:
                record.package_type = 'general'

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

            if record.package_type == 'private':
                record.is_all_inclusive = False

                if record.duration_months == 1:
                    record.included_pt_sessions = 12

                elif record.duration_months == 2:
                    record.included_pt_sessions = 24

                else:
                    record.included_pt_sessions = 0

            elif record.package_type == 'general':

                record.included_pt_sessions = 0

                if record.is_all_inclusive:
                    record.included_physio_sessions_per_month = 2
                    record.included_nutrition_consultations = 1

                else:
                    record.included_physio_sessions_per_month = 0
                    record.included_nutrition_consultations = 0

            elif record.package_type == 'all_inclusive':

                record.is_all_inclusive = False
                record.included_pt_sessions = 0
                record.included_physio_sessions_per_month = 2
                record.included_nutrition_consultations = 1

            record.price = record._get_suggested_price(
                record.package_type,
                record.duration_months,
                record.currency_id.id,
                record.is_all_inclusive,
            )



    @api.constrains(
        'duration_months',
        'price',
        'freeze_days',
    )
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
        'is_all_inclusive',
        'duration_months',
        'included_pt_sessions',
        'included_physio_sessions_per_month',
        'included_nutrition_consultations',
        'price',
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

            if record.is_all_inclusive:
                if record.package_type != 'general':
                    raise ValidationError(
                        'The All-Inclusive option can only be used with '
                        'a General package.'
                    )

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
                        'All-Inclusive membership requires a valid price.'
                    )

            elif record.package_type == 'general':

                if record.included_pt_sessions:
                    raise ValidationError(
                        'General membership cannot include dedicated PT sessions.'
                    )

                if record.included_physio_sessions_per_month:
                    raise ValidationError(
                        'General membership cannot include physiotherapy '
                        'sessions unless it is All-Inclusive.'
                    )

                if record.included_nutrition_consultations:
                    raise ValidationError(
                        'General membership cannot include nutrition '
                        'consultations unless it is All-Inclusive.'
                    )

            elif record.package_type == 'private':

                if record.included_pt_sessions <= 0:
                    raise ValidationError(
                        'Private membership must include PT sessions.'
                    )

                if record.included_physio_sessions_per_month:
                    raise ValidationError(
                        'Private membership cannot include physiotherapy '
                        'sessions.'
                    )

                if record.included_nutrition_consultations:
                    raise ValidationError(
                        'Private membership cannot include nutrition '
                        'consultations.'
                    )

            elif record.package_type == 'all_inclusive':

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
                        'All-Inclusive membership requires a valid price.'
                    )