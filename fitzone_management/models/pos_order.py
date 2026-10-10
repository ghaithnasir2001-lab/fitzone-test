from odoo import api, models


class FitZonePosOrder(models.Model):
    _inherit = 'pos.order'

    def _fitzone_has_active_membership(self, partner):
        if not partner:
            return False

        return bool(self.env['fitzone.membership.subscription'].search_count([
            ('subscriber_id', '=', partner.id),
            ('status', '=', 'active'),
        ]))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        result = super()._onchange_partner_id()

        member_pricelist = self.env['product.pricelist'].search(
            [('name', '=', 'FitZone Member Retail')],
            limit=1,
        )

        if self.partner_id and member_pricelist:
            if self._fitzone_has_active_membership(self.partner_id):
                self.pricelist_id = member_pricelist

        return result
