from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneRehabFile(models.Model):
    _name = 'fitzone.rehab.file'
    _description = 'FitZone Rehabilitation File'
    _order = 'opening_date desc, id desc'

    name = fields.Char(
        string='Rehabilitation Reference',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env[
            'ir.sequence'
        ].next_by_code('fitzone.rehab.file') or 'New',
    )

    injury_id = fields.Many2one(
        'fitzone.injury',
        string='Injury',
        required=True,
        ondelete='restrict',
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        required=True,
        domain=[('is_fitzone_subscriber', '=', True)],
        ondelete='restrict',
    )

    physiotherapist_id = fields.Many2one(
        'hr.employee',
        string='Physiotherapist',
        required=True,
        ondelete='restrict',
    )

    opening_date = fields.Date(
        string='Opening Date',
        required=True,
        default=fields.Date.context_today,
    )

    closing_date = fields.Date(
        string='Closing Date',
    )

    diagnosis = fields.Text(
        string='Diagnosis',
    )

    rehabilitation_plan = fields.Text(
        string='Rehabilitation Plan',
    )

    state = fields.Selection(
        [
            ('open', 'Open'),
            ('closed', 'Closed'),
        ],
        string='Status',
        required=True,
        default='open',
        copy=False,
    )

    @api.constrains('injury_id', 'partner_id')
    def _check_injury_subscriber(self):
        for record in self:
            if (
                record.injury_id
                and record.partner_id
                and record.injury_id.partner_id != record.partner_id
            ):
                raise ValidationError(
                    'The rehabilitation file subscriber must match the injury subscriber.'
                )

    @api.constrains('physiotherapist_id')
    def _check_physiotherapist(self):
        for record in self:
            if (
                record.physiotherapist_id
                and record.physiotherapist_id.fitzone_staff_type
                != 'physiotherapist'
            ):
                raise ValidationError(
                    'The selected employee must be a Physiotherapist.'
                )

    @api.constrains('opening_date', 'closing_date')
    def _check_dates(self):
        for record in self:
            if (
                record.opening_date
                and record.closing_date
                and record.closing_date < record.opening_date
            ):
                raise ValidationError(
                    'Closing Date cannot be earlier than Opening Date.'
                )

    def action_close(self):
        for record in self:
            record.write({
                'state': 'closed',
                'closing_date': record.closing_date or fields.Date.context_today(
                    self
                ),
            })

    def action_reopen(self):
        for record in self:
            record.write({
                'state': 'open',
                'closing_date': False,
            })
