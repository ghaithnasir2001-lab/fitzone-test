from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneTrainerSchedule(models.Model):
    _name = "fitzone.trainer.schedule"
    _description = "FitZone Trainer Working Schedule"
    _order = "day_of_week, start_time"

    _unique_trainer_schedule = models.Constraint(
        "UNIQUE(trainer_id, day_of_week, start_time, end_time)",
        "A trainer cannot have duplicate working schedule entries for the same day and time.",
    )

    trainer_id = fields.Many2one(
        "fitzone.trainer",
        string="Trainer",
        required=True,
        ondelete="cascade",
    )

    day_of_week = fields.Selection(
        [
            ("0", "Sunday"),
            ("1", "Monday"),
            ("2", "Tuesday"),
            ("3", "Wednesday"),
            ("4", "Thursday"),
            ("5", "Friday"),
            ("6", "Saturday"),
        ],
        string="Day",
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
            if schedule.start_time < 0 or schedule.end_time < 0:
                raise ValidationError(
                    "Start time and end time cannot be negative."
                )

            if schedule.start_time > 24 or schedule.end_time > 24:
                raise ValidationError(
                    "Time must be between 00:00 and 24:00."
                )

            if schedule.end_time <= schedule.start_time:
                raise ValidationError(
                    "End time must be later than start time."
                )