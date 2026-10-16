import base64
import csv
import io
import re
import zipfile

from odoo import _, fields, models
from odoo.exceptions import UserError

# Import-ready client files, in the order they must be imported (later files
# link to records created by earlier ones). Key: file name without its number.
CLIENT_FILES = [
    ('departments', 'hr.department'),
    ('employees', 'hr.employee'),
    ('department_managers', 'hr.department'),
    ('trainers', 'fitzone.trainer'),
    ('trainer_schedules', 'fitzone.trainer.schedule'),
    ('facilities', 'fitzone.facility'),
    ('class_services', 'product.template'),
    ('classes', 'fitzone.class'),
    ('membership_packages', 'fitzone.membership.package'),
    ('members', 'res.partner'),
    ('subscriptions', 'fitzone.membership.subscription'),
    ('subscriptions_valid_until', 'fitzone.membership.subscription'),
    ('health_measurements', 'fitzone.health.measurement'),
    ('checkins', 'fitzone.checkin'),
    ('class_sessions', 'fitzone.class.schedule'),
    ('swim_classes', 'fitzone.swimming.slot'),
    ('class_and_swim_bookings', 'fitzone.booking'),
    ('pt_bookings', 'fitzone.trainer.booking'),
    ('physiotherapy_bookings', 'fitzone.booking'),
    ('nutrition_programs', 'fitzone.nutrition.program'),
    ('nutrition_consultations', 'fitzone.nutrition.consultation'),
    ('injury_causes', 'fitzone.injury.cause'),
    ('injuries', 'fitzone.injury'),
    ('equipment_categories', 'maintenance.equipment.category'),
    ('equipment', 'maintenance.equipment'),
    ('open_repairs', 'fitzone.equipment.malfunction'),
    ('suppliers', 'res.partner'),
    ('product_categories', 'product.category'),
    ('products', 'product.template'),
    ('expiry_lots', 'stock.lot'),
    ('stock_counts', 'stock.quant'),
    ('reorder_rules', 'stock.warehouse.orderpoint'),
]
# Counted stock goes in as an inventory count; consultation statuses come from
# the client's records, so re-importing may update them (the module's own
# flag for allowed status changes).
FILE_CONTEXT = {
    'stock.quant': {'inventory_mode': True},
    'fitzone.nutrition.consultation': {'_allow_nutrition_state_transition': True},
}
ORDER = {key: index for index, (key, _model) in enumerate(CLIENT_FILES)}
MODELS = dict(CLIENT_FILES)

IMPORT_OPTIONS = {
    'quoting': '"', 'separator': ',', 'has_headers': True, 'encoding': 'utf-8',
    'date_format': '%Y-%m-%d', 'datetime_format': '%Y-%m-%d %H:%M:%S',
    'float_thousand_separator': ',', 'float_decimal_separator': '.', 'advanced': True,
    'name_create_enabled_fields': {}, 'import_skip_records': [], 'import_set_empty_fields': [],
    'fallback_values': {}, 'limit': 100000, 'skip': 0,
}


class FitZoneClientImport(models.TransientModel):
    _name = 'fitzone.client.import'
    _description = 'Import Client Data'

    file_ids = fields.Many2many('ir.attachment', string='Client Files',
                                help='The import-ready CSV files, or one ZIP containing them.')
    result = fields.Text(readonly=True)
    done = fields.Boolean()

    def _collect_files(self):
        """Return [(key, file name, csv bytes)] sorted in import order."""
        found = []
        for attachment in self.file_ids:
            raw = base64.b64decode(attachment.datas or b'')
            if attachment.name.lower().endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    found += [(name.rsplit('/', 1)[-1], archive.read(name)) for name in archive.namelist()
                              if name.lower().endswith('.csv')]
            else:
                found.append((attachment.name, raw))
        files, unknown = [], []
        for name, raw in found:
            key = re.sub(r'^\d+_', '', name.rsplit('.', 1)[0].lower())
            if key in MODELS:
                files.append((key, name, raw))
            else:
                unknown.append(name)
        if not files:
            raise UserError(_('None of the uploaded files is a FitZone client file.'))
        return sorted(files, key=lambda f: ORDER[f[0]]), unknown

    def action_import(self):
        self.ensure_one()
        files, unknown = self._collect_files()
        context = dict(self.env.context, tz=self.env.user.tz or 'Asia/Amman', import_file=True)
        lines, failed = [], False
        for key, name, raw in files:
            text = raw.decode('utf-8-sig')
            header = next(csv.reader(io.StringIO(text)), [])
            model = MODELS[key]
            file_context = dict(context, **FILE_CONTEXT.get(model, {}))
            importer = self.env['base_import.import'].with_context(file_context).create({
                'res_model': model, 'file': text.encode('utf-8'),
                'file_type': 'text/csv', 'file_name': name,
            })
            outcome = importer.execute_import(header, header, IMPORT_OPTIONS, False)
            errors = [m for m in outcome.get('messages', []) if m.get('type') == 'error']
            if errors:
                failed = True
                lines.append('FAILED  %s' % name)
                for message in errors[:5]:
                    lines.append('        %s' % message.get('message', '').replace('\n', ' '))
                lines.append('Stopped here: the next files depend on this one. '
                             'Fix it and import again; imported records are updated, not duplicated.')
                break
            ids = outcome.get('ids') or []
            if model == 'stock.quant' and ids:
                self.env['stock.quant'].browse(ids).with_context(file_context).action_apply_inventory()
            lines.append('OK      %-34s %5d records' % (name, len(ids)))
        missing = [key for key, _model in CLIENT_FILES if key not in {f[0] for f in files}]
        if missing and not failed:
            lines.append('\nNot uploaded: %s' % ', '.join(missing))
        if unknown:
            lines.append('Ignored (not a FitZone client file): %s' % ', '.join(unknown))
        self.result = '\n'.join(lines)
        self.done = not failed
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'new', 'name': _('Import Client Data'),
        }
