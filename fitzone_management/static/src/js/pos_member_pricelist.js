import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    updatePricelistAndFiscalPosition(newPartner) {
        if (newPartner?.fitzone_has_active_membership) {
            const memberPricelist = this.config.available_pricelist_ids.find(
                (pricelist) => pricelist.name === "FitZone Member Retail"
            );

            if (memberPricelist) {
                const defaultFiscalPosition = this.models[
                    "account.fiscal.position"
                ].find(
                    (position) =>
                        position.id ===
                        this.config.default_fiscal_position_id?.id
                );

                if (!this.config.use_presets || !this.preset_id?.fiscal_position_id) {
                    this.fiscal_position_id = defaultFiscalPosition;
                }

                if (!this.config.use_presets || !this.preset_id?.pricelist_id) {
                    this.setPricelist(memberPricelist);
                }

                return;
            }
        }

        super.updatePricelistAndFiscalPosition(newPartner);
    },
});
