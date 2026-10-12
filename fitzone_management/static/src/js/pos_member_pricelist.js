import { PosOrder } from "@point_of_sale/app/models/pos_order";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";


patch(PosOrder.prototype, {
    updatePricelistAndFiscalPosition(newPartner) {
        if (newPartner?.fitzone_has_active_membership) {
            const memberPricelist = this.config.available_pricelist_ids.find(
                (pricelist) => pricelist.name === "FitZone Member Retail"
            );

            if (memberPricelist) {
                const now = luxon.DateTime.now();

                const hasActiveMemberRule = memberPricelist.item_ids.some(
                    (rule) => {
                        if (rule.date_start && rule.date_start > now) {
                            return false;
                        }

                        if (rule.date_end && rule.date_end <= now) {
                            return false;
                        }

                        return true;
                    }
                );

                if (hasActiveMemberRule) {
                    const defaultFiscalPosition = this.models[
                        "account.fiscal.position"
                    ].find(
                        (position) =>
                            position.id ===
                            this.config.default_fiscal_position_id?.id
                    );

                    if (
                        !this.config.use_presets ||
                        !this.preset_id?.fiscal_position_id
                    ) {
                        this.fiscal_position_id = defaultFiscalPosition;
                    }

                    if (
                        !this.config.use_presets ||
                        !this.preset_id?.pricelist_id
                    ) {
                        this.setPricelist(memberPricelist);
                    }

                    return;
                }
            }
        }

        super.updatePricelistAndFiscalPosition(newPartner);
    },
});


patch(OrderPaymentValidation.prototype, {
    async validateOrder(isForceValidate) {
        const lotValues = [];

        for (const line of this.order.lines) {
            for (const lotLine of line.pack_lot_ids || []) {
                if (lotLine.lot_name) {
                    lotValues.push({
                        product_id: line.product_id.id,
                        lot_name: lotLine.lot_name,
                    });
                }
            }
        }

        if (lotValues.length) {
            let expiredLots;

            try {
                expiredLots = await this.pos.data.call(
                    "pos.order",
                    "fitzone_get_expired_lots",
                    [lotValues]
                );
            } catch {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Expiration Check Failed"),
                    body: _t(
                        "The expiration status of selected lots could not be verified. Please check your connection and try again."
                    ),
                });
                return false;
            }

            if (expiredLots.length) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Expired Product Lot"),
                    body:
                        _t("This sale is blocked because these lots are expired: ") +
                        expiredLots.join(", "),
                });
                return false;
            }
        }

        return super.validateOrder(isForceValidate);
    },
});
