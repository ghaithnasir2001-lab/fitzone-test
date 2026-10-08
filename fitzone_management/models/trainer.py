from odoo import fields, models


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