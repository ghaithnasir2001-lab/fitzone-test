from odoo import api, models


class FitZoneInjuryRehabReport(models.AbstractModel):
    _name = 'report.fitzone_management.report_injury_rehab_document'
    _description = 'FitZone Injury and Rehabilitation Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        injuries = self.env['fitzone.injury'].browse(docids).exists()

        rehab_files = self.env['fitzone.rehab.file'].search([
            ('injury_id', 'in', injuries.ids),
        ])

        rehab_by_injury = {
            rehab.injury_id.id: rehab
            for rehab in rehab_files
        }

        return {
            'doc_ids': injuries.ids,
            'doc_model': 'fitzone.injury',
            'docs': injuries,
            'rehab_by_injury': rehab_by_injury,
        }
