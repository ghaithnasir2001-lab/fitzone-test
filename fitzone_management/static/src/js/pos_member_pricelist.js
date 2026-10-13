import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";


patch(PosOrder.prototype, {
    updatePricelistAndFiscalPosition(newPartner) {
        const defaultFiscalPosition = this.models[
            "account.fiscal.position"
        ].find(
            (position) =>
                position.id === this.config.default_fiscal_position_id?.id
        );

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

        // Non-members must use the standard POS pricelist, never a
        // previously selected member pricelist.
        if (
            !this.config.use_presets ||
            !this.preset_id?.fiscal_position_id
        ) {
            const partnerFiscalPosition = newPartner
                ? this.findFiscalPosition(newPartner.fiscal_position_id)
                : false;
            const isFpAllowed =
                partnerFiscalPosition &&
                this.config.fiscal_position_ids.some(
                    (fp) => fp.id === partnerFiscalPosition.id
                );
            this.fiscal_position_id = isFpAllowed
                ? partnerFiscalPosition
                : defaultFiscalPosition;
        }

        if (
            !this.config.use_presets ||
            !this.preset_id?.pricelist_id
        ) {
            this.setPricelist(this.config.pricelist_id);
        }
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

// Automatically apply FEFO to new POS lines for FitZone health products
// and supplements. Other products and edits to existing lot assignments
// continue through Odoo's standard implementation.
patch(PosStore.prototype, {
    async editLots(product, packLotLinesToEdit) {
        const template = product.product_tmpl_id;
        const isFitZoneFefoProduct =
            template?.fitzone_kind === "retail" &&
            ["health", "supplement"].includes(template?.product_type);

        if (!isFitZoneFefoProduct || packLotLinesToEdit.length) {
            return super.editLots(product, packLotLinesToEdit);
        }

        let lots;
        try {
            lots = await this.data.call("pos.order.line", "get_existing_lots", [
                this.company.id,
                this.config.id,
                product.id,
            ]);
        } catch {
            // Preserve Odoo's standard communication-error handling.
            return super.editLots(product, packLotLinesToEdit);
        }

        // Let Odoo handle its normal no-lots and lot-creation cases.
        if (!lots?.length) {
            return super.editLots(product, packLotLinesToEdit);
        }

        const usedLotsQty = this.models["pos.pack.operation.lot"]
            .filter(
                (lot) =>
                    lot.pos_order_line_id?.product_id?.id === product.id &&
                    lot.pos_order_line_id?.order_id?.state === "draft"
            )
            .reduce((acc, lot) => {
                if (!acc[lot.lot_name]) {
                    acc[lot.lot_name] = { total: 0, currentOrderCount: 0 };
                }
                acc[lot.lot_name].total += lot.pos_order_line_id?.qty || 0;

                if (lot.pos_order_line_id?.order_id?.id === this.selectedOrder.id) {
                    acc[lot.lot_name].currentOrderCount +=
                        lot.pos_order_line_id?.qty || 0;
                }
                return acc;
            }, {});

        const availableLots = lots.filter(
            (lot) =>
                lot.product_qty >
                (usedLotsQty[lot.name]?.total || 0)
        );

        const now = Date.now();
        const getExpirationTime = (lot) => {
            if (!lot.expiration_date) {
                return Number.POSITIVE_INFINITY;
            }
            // Odoo Datetime values are returned as UTC-naive SQL strings.
            const timestamp = Date.parse(
                `${lot.expiration_date.replace(" ", "T")}Z`
            );
            return Number.isFinite(timestamp)
                ? timestamp
                : Number.NEGATIVE_INFINITY;
        };

        const eligibleLots = availableLots
            .filter((lot) => {
                if (!lot.expiration_date) {
                    return false;
                }
                const expirationTime = getExpirationTime(lot);
                return Number.isFinite(expirationTime) && expirationTime > now;
            })
            .sort((a, b) => getExpirationTime(a) - getExpirationTime(b));

        if (eligibleLots.length) {
            return {
                newPackLotLines: [{ lot_name: eligibleLots[0].name }],
            };
        }

        if (availableLots.length) {
            this.dialog.add(AlertDialog, {
                title: _t("No unexpired lots available"),
                body: _t(
                    "No available lot has a valid, future expiration date. Please check the stock before continuing."
                ),
            });
            return null;
        }

        return super.editLots(product, packLotLinesToEdit);
    },
});
