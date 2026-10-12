from odoo import api, fields, models, _
from odoo.exceptions import UserError

MANAGEMENT_GROUP = "fitzone_management.group_fitzone_management"


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    fitzone_status = fields.Selection(
        [
            ("fit_for_use", "Fit for Use"),
            ("out_of_service", "Out of Service"),
        ],
        string="FitZone Equipment Status",
        default="fit_for_use",
        required=True,
        tracking=True,
    )

    def write(self, vals):
        if vals.get("fitzone_status") == "fit_for_use":
            if not self.env.user.has_group(MANAGEMENT_GROUP):
                raise UserError(
                    _("Only FitZone Management can return equipment to Fit for Use.")
                )

            for equipment in self:
                open_requests = self.env["maintenance.request"].search_count([
                    ("equipment_id", "=", equipment.id),
                    ("stage_id.done", "=", False),
                ])

                pending_malfunctions = self.env[
                    "fitzone.equipment.malfunction"
                ].search_count([
                    ("equipment_id", "=", equipment.id),
                    ("approval_state", "=", "pending"),
                ])

                if open_requests or pending_malfunctions:
                    raise UserError(
                        _(
                            "Equipment cannot return to Fit for Use while "
                            "maintenance is open or a malfunction is awaiting approval."
                        )
                    )

        return super().write(vals)

    
    def action_fitzone_return_to_service(self):
        if not self.env.user.has_group(MANAGEMENT_GROUP):
            raise UserError(
                _("Only FitZone Management can return equipment to Fit for Use.")
            )

        for equipment in self:
            open_requests = self.env["maintenance.request"].search_count([
                ("equipment_id", "=", equipment.id),
                ("stage_id.done", "=", False),
                ("archive", "=", False),
            ])

            pending_malfunctions = self.env[
                "fitzone.equipment.malfunction"
            ].search_count([
                ("equipment_id", "=", equipment.id),
                ("approval_state", "=", "pending"),
            ])

            if open_requests or pending_malfunctions:
                raise UserError(
                    _(
                        "Resolve open maintenance requests and pending "
                        "malfunctions before returning this equipment to service."
                    )
                )

        self.write({"fitzone_status": "fit_for_use"})
        return True

class FitZoneEquipmentMalfunction(models.Model):
    _name = "fitzone.equipment.malfunction"
    _description = "FitZone Equipment Malfunction"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "reported_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )

    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Equipment",
        required=True,
        ondelete="restrict",
        tracking=True,
    )

    reported_by = fields.Many2one(
        "res.users",
        string="Reported By",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )

    reported_date = fields.Datetime(
        string="Reported On",
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )

    description = fields.Text(
        string="Malfunction Description",
        required=True,
        tracking=True,
    )

    failure_source = fields.Selection(
        [
            ("internal", "Internal Malfunction"),
            ("manufacturing_defect", "Manufacturing Defect"),
        ],
        string="Failure Source",
        default="internal",
        required=True,
        tracking=True,
    )

    supplier_notes = fields.Text(
        string="Supplier / Manufacturer Notes",
        help="Record supplier handling for manufacturing defects.",
    )

    approval_state = fields.Selection(
        [
            ("pending", "Pending Management Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Approval Status",
        default="pending",
        required=True,
        readonly=True,
        tracking=True,
    )

    maintenance_request_id = fields.Many2one(
        "maintenance.request",
        string="Maintenance Request",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("base.group_user"):
            raise UserError(
                _("Only internal users can report equipment malfunctions.")
            )

        sequence = self.env["ir.sequence"]

        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "New":
                vals["name"] = (
                    sequence.next_by_code("fitzone.equipment.malfunction")
                    or "New"
                )

            # Approval and request linkage are controlled by the workflow.
            vals["approval_state"] = "pending"
            vals.pop("maintenance_request_id", None)

            # The reporting user and timestamp must reflect the actual report.
            vals["reported_by"] = self.env.user.id
            vals["reported_date"] = fields.Datetime.now()

        records = super().create(vals_list)

        # Every new malfunction immediately makes the equipment unavailable.
        for record in records:
            record.equipment_id.sudo().write({
                "fitzone_status": "out_of_service",
            })

        return records

    def write(self, vals):
        protected = {
            "name",
            "equipment_id",
            "reported_by",
            "reported_date",
            "approval_state",
            "maintenance_request_id",
        }

        if protected.intersection(vals):
            if not self.env.user.has_group(MANAGEMENT_GROUP):
                raise UserError(
                    _(
                        "Only FitZone Management can change protected "
                        "malfunction information or approval."
                    )
                )

        if "approval_state" in vals:
            raise UserError(
                _("Use the Approve or Reject action to change malfunction status.")
            )

        if "maintenance_request_id" in vals:
            raise UserError(
                _("The maintenance request must be linked through the approval workflow.")
            )

        return super().write(vals)

    def action_approve(self):
        if not self.env.user.has_group(MANAGEMENT_GROUP):
            raise UserError(
                _("Only FitZone Management can approve malfunctions.")
            )

        Request = self.env["maintenance.request"]

        for record in self:
            if record.approval_state != "pending":
                raise UserError(
                    _("Only pending malfunctions can be approved.")
                )

            if record.maintenance_request_id:
                raise UserError(
                    _("A maintenance request already exists for this malfunction.")
                )

            existing_request = Request.search_count([
                ("fitzone_malfunction_id", "=", record.id),
            ])

            if existing_request:
                raise UserError(
                    _("A maintenance request already exists for this malfunction.")
                )

            # The request creation method validates the pending report,
            # the manager's permissions, and the equipment relationship.
            request = Request.create({
                "name": _("Repair: %s", record.equipment_id.display_name),
                "description": record.description,
                "equipment_id": record.equipment_id.id,
                "maintenance_type": "corrective",
                "fitzone_malfunction_id": record.id,
                "fitzone_estimated_cost": 0.0,
                "fitzone_estimated_hours": 0.0,
            })

            # Change the report status only after request creation succeeds.
            super(FitZoneEquipmentMalfunction, record).write({
                "approval_state": "approved",
                "maintenance_request_id": request.id,
            })

    def action_reject(self):
        if not self.env.user.has_group(MANAGEMENT_GROUP):
            raise UserError(
                _("Only FitZone Management can reject malfunctions.")
            )

        for record in self:
            if record.approval_state != "pending":
                raise UserError(
                    _("Only pending malfunctions can be rejected.")
                )

            super(FitZoneEquipmentMalfunction, record).write({
                "approval_state": "rejected",
            })


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    fitzone_malfunction_id = fields.Many2one(
        "fitzone.equipment.malfunction",
        string="Related Malfunction",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    fitzone_approval_state = fields.Selection(
        [
            ("pending", "Pending Management Approval"),
            ("approved", "Approved"),
        ],
        string="FitZone Approval",
        default="pending",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
    )

    fitzone_estimated_cost = fields.Monetary(
        string="Estimated Maintenance Cost",
        currency_field="company_currency_id",
        tracking=True,
    )

    fitzone_estimated_hours = fields.Float(
        string="Estimated Maintenance Hours",
        tracking=True,
    )

    fitzone_actual_hours = fields.Float(
        string="Actual Maintenance Hours",
        tracking=True,
    )

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            maintenance_type = vals.get("maintenance_type", "corrective")

            if maintenance_type == "corrective":
                malfunction_id = vals.get("fitzone_malfunction_id")

                if not malfunction_id:
                    raise UserError(
                        _(
                            "Corrective maintenance must be created "
                            "from a reported malfunction."
                        )
                    )

                malfunction = self.env[
                    "fitzone.equipment.malfunction"
                ].browse(malfunction_id).exists()

                if not malfunction:
                    raise UserError(
                        _("The related malfunction does not exist.")
                    )

                if not self.env.user.has_group(MANAGEMENT_GROUP):
                    raise UserError(
                        _("Only FitZone Management can approve repair work.")
                    )

                if malfunction.approval_state != "pending":
                    raise UserError(
                        _("Only pending malfunctions can create a repair request.")
                    )

                if vals.get("equipment_id") != malfunction.equipment_id.id:
                    raise UserError(
                        _(
                            "The repair request equipment must match "
                            "the reported malfunction equipment."
                        )
                    )

                if malfunction.maintenance_request_id:
                    raise UserError(
                        _("A maintenance request already exists for this malfunction.")
                    )

                duplicate = self.search_count([
                    ("fitzone_malfunction_id", "=", malfunction.id),
                ])

                if duplicate:
                    raise UserError(
                        _("A maintenance request already exists for this malfunction.")
                    )

                vals["fitzone_approval_state"] = "approved"

            else:
                # Preventive work is not allowed to start before approval.
                vals["fitzone_approval_state"] = "pending"

        requests = super().create(vals_list)

        # Approved repair requests keep their equipment out of service.
        for request in requests:
            if (
                request.maintenance_type == "corrective"
                and request.equipment_id
            ):
                request.equipment_id.sudo().write({
                    "fitzone_status": "out_of_service",
                })

        return requests

    def action_approve_fitzone_maintenance(self):
        if not self.env.user.has_group(MANAGEMENT_GROUP):
            raise UserError(
                _("Only FitZone Management can approve maintenance.")
            )

        for request in self:
            if request.maintenance_type != "preventive":
                raise UserError(
                    _(
                        "Corrective maintenance is approved through "
                        "its malfunction report."
                    )
                )

            if request.fitzone_approval_state != "pending":
                raise UserError(
                    _("This maintenance request is not pending approval.")
                )

            super(MaintenanceRequest, request).write({
                "fitzone_approval_state": "approved",
            })

    
    def write(self, vals):
        if "fitzone_approval_state" in vals:
            raise UserError(
                _("Use the maintenance approval action to approve preventive work.")
            )

        if "fitzone_malfunction_id" in vals:
            raise UserError(
                _("The related malfunction cannot be changed manually.")
            )

        # Maintenance work cannot progress before management approval.
        work_fields = {
            "stage_id",
            "user_id",
            "schedule_date",
            "duration",
            "close_date",
        }

        if work_fields.intersection(vals):
            for request in self:
                if request.fitzone_approval_state != "approved":
                    raise UserError(
                        _("Maintenance must be approved before work can begin.")
                    )

        result = super().write(vals)

        # Equipment stays out of service even when the repair is completed.
        if "stage_id" in vals:
            for request in self:
                if request.equipment_id:
                    request.equipment_id.sudo().write({
                        "fitzone_status": "out_of_service",
                    })

        return result