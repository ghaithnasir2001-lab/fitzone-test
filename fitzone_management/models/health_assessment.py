from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FitZoneHealthAssessment(models.Model):
    _name = 'fitzone.health.assessment'
    _description = 'FitZone Health Assessment'
    _order = 'assessment_date desc, id desc'

    name = fields.Char(
        string='Assessment Reference',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env[
            'ir.sequence'
        ].next_by_code('fitzone.health.assessment'),
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        required=True,
    )

    assessment_type = fields.Selection(
        [
            ('initial', 'Initial Health Assessment'),
            ('injury', 'Injury Health Assessment'),
        ],
        string='Assessment Type',
        required=True,
        default='initial',
    )

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('completed', 'Completed'),
        ],
        string='Status',
        required=True,
        default='draft',
        copy=False,
    )

    assessment_date = fields.Date(
        string='Assessment Date',
        required=True,
        default=fields.Date.context_today,
    )

    performed_by = fields.Many2one(
        'hr.employee',
        string='Performed By',
        required=True,
        default=lambda self: self._default_performed_by(),
    )

    assigned_to = fields.Many2one(
        'hr.employee',
        string='Assigned To',
        required=True,
    )

    medical_notes = fields.Text(
        string='Medical Notes',
    )

    health_status = fields.Char(
        string='Health Status',
    )

    restrictions = fields.Text(
        string='Restrictions',
    )

    notes = fields.Text(
        string='Notes',
    )

    measurement_ids = fields.One2many(
        'fitzone.health.measurement',
        'assessment_id',
        string='Measurements',
    )

    @api.model
    def _default_performed_by(self):
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.user.id)],
            limit=1,
        )

        if employee and employee.fitzone_staff_type == 'nurse':
            return employee.id

        return False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            performed_by_id = vals.get('performed_by')

            if not performed_by_id:
                raise ValidationError(
                    'Please select the Nurse who performed the assessment.'
                )

            performed_by = self.env['hr.employee'].browse(
                performed_by_id
            ).exists()

            if (
                not performed_by
                or performed_by.fitzone_staff_type != 'nurse'
            ):
                raise ValidationError(
                    'Performed By must be a Nurse.'
                )

        return super().create(vals_list)

    @api.constrains('partner_id')
    def _check_subscriber(self):
        for record in self:
            if (
                record.partner_id
                and not record.partner_id.is_fitzone_subscriber
            ):
                raise ValidationError(
                    'A health assessment can only be created for a FitZone subscriber.'
                )

    @api.constrains('partner_id', 'assessment_type')
    def _check_initial_assessment_limit(self):
        for record in self:
            if (
                not record.partner_id
                or record.assessment_type != 'initial'
            ):
                continue

            duplicate_initial = self.search_count([
                ('id', '!=', record.id),
                ('partner_id', '=', record.partner_id.id),
                ('assessment_type', '=', 'initial'),
            ])

            if duplicate_initial:
                raise ValidationError(
                    'A subscriber can have only one Initial Health Assessment.'
                )

    @api.constrains(
        'assessment_type',
        'performed_by',
        'assigned_to',
    )
    def _check_staff_assignments(self):
        for record in self:
            if (
                record.performed_by
                and record.performed_by.fitzone_staff_type != 'nurse'
            ):
                raise ValidationError(
                    'The assessment must be performed by a Nurse.'
                )

            if not record.assigned_to:
                continue

            expected_staff_type = (
                'nutritionist'
                if record.assessment_type == 'initial'
                else 'physiotherapist'
            )

            if record.assigned_to.fitzone_staff_type != expected_staff_type:
                role_name = (
                    'Nutritionist'
                    if expected_staff_type == 'nutritionist'
                    else 'Physiotherapist'
                )

                raise ValidationError(
                    'This assessment must be assigned to a %s.'
                    % role_name
                )

    def action_mark_completed(self):
        for record in self:
            if record.state == 'completed':
                continue

            if self.env.user.has_group('base.group_system'):
                record.with_context(
                    fitzone_allow_complete=True
                ).write({
                    'state': 'completed',
                })
                continue

            employee = self.env['hr.employee'].search(
                [('user_id', '=', self.env.user.id)],
                limit=1,
            )

            if not employee or employee.fitzone_staff_type != 'nurse':
                raise ValidationError(
                    'Only a Nurse or Administrator can mark a health assessment as completed.'
                )

            record.with_context(
                fitzone_allow_complete=True
            ).write({
                'state': 'completed',
            })

    def action_reset_to_draft(self):
        for record in self:
            record.write({
                'state': 'draft',
            })

    def write(self, vals):
        if 'performed_by' in vals:
            for record in self:
                if (
                    record.state == 'completed'
                    and vals['performed_by'] != record.performed_by.id
                ):
                    raise ValidationError(
                        'Performed By cannot be changed after the assessment is completed.'
                    )

        if vals.get('state') == 'completed' and not self.env.context.get(
            'fitzone_allow_complete'
        ):
            raise ValidationError(
                'Use the Mark as Completed action to complete a health assessment.'
            )

        return super().write(vals)


class FitZoneHealthMeasurement(models.Model):
    _name = 'fitzone.health.measurement'
    _description = 'FitZone Health Measurement'
    _order = 'measurement_date desc, id desc'

    partner_id = fields.Many2one(
        'res.partner',
        string='Subscriber',
        required=True,
    )

    assessment_id = fields.Many2one(
        'fitzone.health.assessment',
        string='Assessment',
    )

    measurement_date = fields.Date(
        string='Measurement Date',
        required=True,
        default=fields.Date.context_today,
    )

    weight = fields.Float(
        string='Weight',
    )

    height = fields.Float(
        string='Height',
    )

    bmi = fields.Float(
        string='BMI',
    )

    body_fat = fields.Float(
        string='Body Fat',
    )

    muscle_mass = fields.Float(
        string='Muscle Mass',
    )

    blood_pressure = fields.Char(
        string='Blood Pressure',
    )

    notes = fields.Text(
        string='Notes',
    )

    recorded_by = fields.Many2one(
        'hr.employee',
        string='Recorded By',
    )

    @api.constrains('partner_id')
    def _check_subscriber(self):
        for record in self:
            if (
                record.partner_id
                and not record.partner_id.is_fitzone_subscriber
            ):
                raise ValidationError(
                    'A health measurement can only be created for a FitZone subscriber.'
                )

    @api.constrains(
        'weight',
        'height',
        'bmi',
        'body_fat',
        'muscle_mass',
        'blood_pressure',
    )
    def _check_measurement_values(self):
        for record in self:
            measurements = {
                'Weight': record.weight,
                'Height': record.height,
                'BMI': record.bmi,
                'Body Fat': record.body_fat,
                'Muscle Mass': record.muscle_mass,
            }

            for label, value in measurements.items():
                if value < 0:
                    raise ValidationError(
                        '%s cannot be negative.' % label
                    )

            if record.blood_pressure:
                blood_pressure = record.blood_pressure.strip()

                if blood_pressure.startswith('-'):
                    raise ValidationError(
                        'Blood Pressure cannot be negative.'
                    )

                if '/' in blood_pressure:
                    systolic, diastolic = blood_pressure.split('/', 1)

                    if systolic.strip().startswith('-'):
                        raise ValidationError(
                            'Blood Pressure cannot contain negative values.'
                        )

                    if diastolic.strip().startswith('-'):
                        raise ValidationError(
                            'Blood Pressure cannot contain negative values.'
                        )

    @api.constrains('assessment_id', 'partner_id')
    def _check_assessment_subscriber(self):
        for record in self:
            if (
                record.assessment_id
                and record.partner_id
                and record.assessment_id.partner_id != record.partner_id
            ):
                raise ValidationError(
                    'The measurement subscriber must match the assessment subscriber.'
                )


class ResPartner(models.Model):
    _inherit = 'res.partner'

    health_assessment_ids = fields.One2many(
        'fitzone.health.assessment',
        'partner_id',
        string='Health Assessments',
    )

    health_assessment_status = fields.Selection(
        [
            ('required', 'Health Assessment Required'),
            ('completed', 'Assessment Completed'),
        ],
        string='Health Assessment Status',
        compute='_compute_health_assessment_status',
        store=True,
    )

    @api.depends(
        'is_fitzone_subscriber',
        'health_assessment_ids.assessment_type',
        'health_assessment_ids.state',
    )
    def _compute_health_assessment_status(self):
        for partner in self:
            if not partner.is_fitzone_subscriber:
                partner.health_assessment_status = False
                continue

            initial_completed = any(
                assessment.assessment_type == 'initial'
                and assessment.state == 'completed'
                for assessment in partner.health_assessment_ids
            )

            partner.health_assessment_status = (
                'completed'
                if initial_completed
                else 'required'
            )
