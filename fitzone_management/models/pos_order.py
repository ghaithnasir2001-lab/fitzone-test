from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    @api.model
    def fitzone_get_expired_lots(self, lot_values):
        """Return expired lots belonging to FitZone health products or supplements."""
        expired_lots = []
        Lot = self.env["stock.lot"].sudo()
        Product = self.env["product.product"].sudo()
        now = fields.Datetime.now()

        for value in lot_values:
            product_id = value.get("product_id")
            lot_name = value.get("lot_name")

            if not product_id or not lot_name:
                continue

            product = Product.browse(product_id).exists()
            if not product:
                continue

            template = product.product_tmpl_id

            if (
                template.fitzone_kind != "retail"
                or template.product_type not in ("health", "supplement")
            ):
                continue

            lot = Lot.search(
                [
                    ("product_id", "=", product.id),
                    ("name", "=", lot_name),
                ],
                limit=1,
            )

            if lot and lot.expiration_date and lot.expiration_date <= now:
                expired_lots.append(
                    "%s — Lot %s" % (product.display_name, lot.name)
                )

        return expired_lots

    def _fitzone_validate_expired_lots(self):
        """Block completed POS sales containing expired FitZone retail lots."""
        for order in self:
            lot_values = []

            for line in order.lines:
                for lot_line in line.pack_lot_ids:
                    lot_values.append({
                        "product_id": line.product_id.id,
                        "lot_name": lot_line.lot_name,
                    })

            expired_lots = self.env["pos.order"].fitzone_get_expired_lots(
                lot_values,
            )

            if expired_lots:
                raise ValidationError(
                    _("Cannot complete this sale because these lots are expired: %s")
                    % ", ".join(expired_lots)
                )

    def _process_saved_order(self, draft):
        self.ensure_one()

        if not draft and self.state != "cancel":
            self._fitzone_validate_expired_lots()

        return super()._process_saved_order(draft)
