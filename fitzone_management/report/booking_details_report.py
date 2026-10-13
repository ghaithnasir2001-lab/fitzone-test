from odoo import api, models


class FitZoneBookingDetailsReport(models.AbstractModel):
    _name = 'report.fitzone_management.report_booking_details_document'
    _description = 'FitZone Booking Details PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        bookings = self.env['fitzone.booking'].browse(docids).exists()

        return {
            'doc_ids': bookings.ids,
            'doc_model': 'fitzone.booking',
            'docs': bookings,
        }