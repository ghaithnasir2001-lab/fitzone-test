from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneTrainerSchedule(models.Model):
    _name = "fitzone.trainer.schedule"
    _description = "FitZone Trainer Working Schedule"
    _order = "schedule_date, start_time"

    trainer_id = fields.Many2one(
        "fitzone.trainer",
        string="Trainer",
        required=True,
        ondelete="cascade",
    )

    schedule_date = fields.Date(
        string="Date",
        required=True,
    )

    start_time = fields.Float(
        string="Start Time",
        required=True,
    )

    end_time = fields.Float(
        string="End Time",
        required=True,
    )

    active = fields.Boolean(
        string="Available",
        default=True,
    )

    @api.constrains("start_time", "end_time")
    def _check_schedule_time(self):
        for schedule in self:
            if schedule.end_time <= schedule.start_time:
                raise ValidationError(
                    "End time must be later than start time."
                )
