from odoo import api, models


class FitZoneRehabilitationFilesReport(models.AbstractModel):
    _name = (
        'report.fitzone_management.'
        'report_rehabilitation_files_document'
    )
    _description = 'FitZone Rehabilitation Files Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['fitzone.rehab.file'].browse(docids).exists()

        return {
            'doc_ids': docs.ids,
            'doc_model': 'fitzone.rehab.file',
            'docs': docs,
        }
