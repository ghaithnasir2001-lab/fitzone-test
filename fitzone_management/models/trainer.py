from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneTrainer(models.Model):
    _name = "fitzone.trainer"
    _description = "FitZone Trainer"
    _order = "name"

    name = fields.Char(
        string="Trainer Name",
        required=True
    )

    specialization = fields.Char(
        string="Specialization"
    )

    phone = fields.Char(
        string="Phone"
    )

    email = fields.Char(
        string="Email"
    )

    active = fields.Boolean(
        string="Active",
        default=True
    )

    working_schedule_ids = fields.One2many(
        "fitzone.trainer.schedule",
        "trainer_id",
        string="Working Schedule"
    )

    @api.constrains("email", "phone")
    def _check_unique_contact_info(self):
        for trainer in self:
            if trainer.email:
                duplicate_email = self.search([
                    ("id", "!=", trainer.id),
                    ("email", "=", trainer.email),
                ], limit=1)

                if duplicate_email:
                    raise ValidationError(
                        "A trainer with this email already exists."
                    )

            if trainer.phone:
                duplicate_phone = self.search([
                    ("id", "!=", trainer.id),
                    ("phone", "=", trainer.phone),
                ], limit=1)

                if duplicate_phone:
                    raise ValidationError(
                        "A trainer with this phone number already exists."
                    )