from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fitzone_injury_ids = fields.One2many(
        'fitzone.injury',
        'partner_id',
        string='Injuries',
    )

    fitzone_rehab_file_ids = fields.One2many(
        'fitzone.rehab.file',
        'partner_id',
        string='Rehabilitation Files',
    )
