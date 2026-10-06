from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_fitzone_subscriber = fields.Boolean(
        string='FitZone Subscriber',
        default=False
    )

    subscriber_notes = fields.Text(
        string='Subscriber Notes'
    )

    @api.constrains('is_fitzone_subscriber', 'phone', 'email')
    def _check_duplicate_subscriber(self):
        for record in self:
            if not record.is_fitzone_subscriber:
                continue

            if record.phone:
                duplicate_phone = self.search([
                    ('id', '!=', record.id),
                    ('is_fitzone_subscriber', '=', True),
                    ('phone', '=', record.phone),
                ], limit=1)

                if duplicate_phone:
                    raise ValidationError(
                        'A FitZone Subscriber with this phone number already exists.'
                    )

            if record.email:
                duplicate_email = self.search([
                    ('id', '!=', record.id),
                    ('is_fitzone_subscriber', '=', True),
                    ('email', '=', record.email),
                ], limit=1)

                if duplicate_email:
                    raise ValidationError(
                        'A FitZone Subscriber with this email already exists.'
                    )