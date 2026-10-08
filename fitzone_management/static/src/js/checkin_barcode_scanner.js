/** @odoo-module **/

import { registry } from "@web/core/registry";
import { scanBarcode } from "@web/core/barcode/barcode_dialog";

const checkinBarcodeScanner = {
    start(env) {
        console.log("FitZone Barcode Scanner loaded.");

        document.addEventListener(
            "click",
            async (event) => {
                const button = event.target.closest(
                    "#fitzone_scan_barcode"
                );

                if (!button) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                try {
                    const barcode = await scanBarcode(
                        env,
                        "environment"
                    );

                    console.log(
                        "FitZone barcode detected:",
                        barcode
                    );

                    const barcodeInput = document.querySelector(
                        '.o_field_widget[name="barcode"] input'
                    );

                    if (barcodeInput) {
                        barcodeInput.focus();

                        const nativeInputValueSetter =
                            Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype,
                                "value"
                            ).set;

                        nativeInputValueSetter.call(
                            barcodeInput,
                            barcode
                        );

                        barcodeInput.dispatchEvent(
                            new Event("input", {
                                bubbles: true,
                            })
                        );

                        barcodeInput.dispatchEvent(
                            new Event("change", {
                                bubbles: true,
                            })
                        );

                        barcodeInput.blur();

                        console.log(
                            "FitZone barcode inserted:",
                            barcode
                        );
                    } else {
                        console.error(
                            "FitZone barcode input not found."
                        );
                    }
                } catch (error) {
                    console.error(
                        "FitZone barcode scanner error:",
                        error
                    );
                }
            },
            true
        );
    },
};

registry.category("services").add(
    "fitzone_checkin_barcode_scanner",
    checkinBarcodeScanner
);