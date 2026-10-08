from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneCheckin(models.Model):
    _name = 'fitzone.checkin'
    _description = 'FitZone Check-in'
    _order = 'checkin_datetime desc, id desc'

    name = fields.Char(
        string='Check-in Reference',
        required=True,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'fitzone.checkin'
        ) or 'New',
        copy=False,
        readonly=True,
    )

    barcode = fields.Char(
        string='Membership Barcode',
        required=True,
        copy=False,
        index=True,
    )

    subscriber_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        readonly=True,
        domain=[('is_fitzone_subscriber', '=', True)],
    )

    membership_id = fields.Many2one(
        'fitzone.membership.subscription',
        string='Membership',
        readonly=True,
    )

    checkin_datetime = fields.Datetime(
        string='Check-in Date & Time',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )

    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('checked_in', 'Checked In'),
        ],
        string='Status',
        default='draft',
        required=True,
        readonly=True,
    )

    @api.onchange('barcode')
    def _onchange_barcode(self):
        for record in self:
            record.subscriber_id = False
            record.membership_id = False

            if not record.barcode:
                return

            membership_model = self.env[
                'fitzone.membership.subscription'
            ]

            result = membership_model.verify_barcode(record.barcode)

            if not result['allowed']:
                return {
                    'warning': {
                        'title': 'Membership Not Available',
                        'message': result['reason'],
                    }
                }

            membership = result['membership']

            record.subscriber_id = membership.subscriber_id
            record.membership_id = membership

    def action_check_in(self):
        membership_model = self.env[
            'fitzone.membership.subscription'
        ]

        for record in self:
            if record.status == 'checked_in':
                raise ValidationError(
                    'This check-in has already been completed.'
                )

            result = membership_model.verify_barcode(record.barcode)

            if not result['allowed']:
                raise ValidationError(result['reason'])

            membership = result['membership']

            record.write({
                'subscriber_id': membership.subscriber_id.id,
                'membership_id': membership.id,
                'checkin_datetime': fields.Datetime.now(),
                'status': 'checked_in',
            })

        return True