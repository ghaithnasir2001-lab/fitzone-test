from odoo import api, models


class FitZoneMembershipDetailsReport(models.AbstractModel):
    _name = 'report.fitzone_management.report_membership_details_document'
    _description = 'FitZone Membership Details PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        subscriptions = self.env[
            'fitzone.membership.subscription'
        ].browse(docids).exists()

        return {
            'doc_ids': subscriptions.ids,
            'doc_model': 'fitzone.membership.subscription',
            'docs': subscriptions,
        }
