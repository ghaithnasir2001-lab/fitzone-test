from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneInjury(models.Model):
    _name = 'fitzone.injury'
    _description = 'FitZone Injury'
    _order = 'injury_date desc, id desc'

    name = fields.Char(
        string='Injury Reference',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env[
            'ir.sequence'
        ].next_by_code('fitzone.injury') or 'New',
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        required=True,
        domain=[('is_fitzone_subscriber', '=', True)],
        ondelete='restrict',
    )

    appointment_id = fields.Many2one(
        'fitzone.booking',
        string='Booking',
        ondelete='set null',
    )

    service_id = fields.Many2one(
        'product.template',
        string='Related Service',
        ondelete='set null',
    )

    facility_id = fields.Many2one(
        'fitzone.facility',
        string='Facility',
        ondelete='set null',
    )

    cause_id = fields.Many2one(
        'fitzone.injury.cause',
        string='Cause',
        required=True,
        ondelete='restrict',
    )

    reported_by = fields.Many2one(
        'hr.employee',
        string='Reported By',
        required=True,
        ondelete='restrict',
    )

    injury_date = fields.Date(
        string='Injury Date',
        required=True,
        default=fields.Date.context_today,
    )

    description = fields.Text(
        string='Description',
    )

    severity = fields.Char(
        string='Severity',
    )

    restrictions = fields.Text(
        string='Restrictions',
    )

    forbidden_movements = fields.Text(
        string='Forbidden Movements',
    )

    state = fields.Selection(
        [
            ('reported', 'Reported'),
            ('referred', 'Referred to Physiotherapy'),
        ],
        string='Status',
        required=True,
        default='reported',
        copy=False,
    )

    @api.constrains('partner_id')
    def _check_subscriber(self):
        for record in self:
            if (
                record.partner_id
                and not record.partner_id.is_fitzone_subscriber
            ):
                raise ValidationError(
                    'An injury can only be recorded for a FitZone subscriber.'
                )

    @api.constrains('reported_by')
    def _check_reported_by_trainer(self):
        for record in self:
            if (
                record.reported_by
                and record.reported_by.fitzone_staff_type != 'trainer'
            ):
                raise ValidationError(
                    'An injury must be reported by a Trainer.'
                )

    def action_refer_to_physiotherapy(self):
        for record in self:
            record.state = 'referred'
