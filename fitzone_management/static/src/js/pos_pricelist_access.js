import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";

function hasCurrentRule(pricelist) {
    const rules = pricelist?.item_ids || [];

    // A pricelist without rules uses normal product prices.
    if (!rules.length) {
        return true;
    }

    const now = luxon.DateTime.now();

    return rules.some((rule) => {
        if (rule.date_start && rule.date_start > now) {
            return false;
        }
        if (rule.date_end && rule.date_end < now) {
            return false;
        }
        return true;
    });
}

patch(ControlButtons.prototype, {
    getPricelistList() {
        const selectionList = super.getPricelistList();
        const config = this.pos.config;
        const partner = this.currentOrder?.getPartner();

        const standardPricelist = config.pricelist_id;
        const memberPricelist = config.availablePricelists.find(
            (pricelist) => pricelist.name === "FitZone Member Retail"
        );

        const isActiveSubscriber = Boolean(
            partner?.fitzone_has_active_membership
        );

        const allowedPricelist =
            isActiveSubscriber &&
            memberPricelist &&
            hasCurrentRule(memberPricelist)
                ? memberPricelist
                : standardPricelist;

        return selectionList.filter(
            (entry) => entry.item?.id === allowedPricelist?.id
        );
    },
});
