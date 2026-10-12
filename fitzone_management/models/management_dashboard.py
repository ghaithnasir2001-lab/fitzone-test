from datetime import timedelta

from odoo import api, fields, models


class FitZoneManagementDashboard(models.TransientModel):
    _name = 'fitzone.management.dashboard'
    _description = 'FitZone Management Dashboard'

    name = fields.Char(default='Management Dashboard')

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )

    # Financial Overview
    revenue_today = fields.Monetary(
        string='Revenue Collected Today',
        currency_field='currency_id',
        compute='_compute_dashboard_kpis',
    )
    revenue_month = fields.Monetary(
        string='Revenue Collected This Month',
        currency_field='currency_id',
        compute='_compute_dashboard_kpis',
    )
    outstanding_payments = fields.Monetary(
        string='Outstanding Payments',
        currency_field='currency_id',
        compute='_compute_dashboard_kpis',
    )

    # Membership Overview
    active_memberships = fields.Integer(
        string='Active Memberships',
        compute='_compute_dashboard_kpis',
    )
    expiring_soon = fields.Integer(
        string='Expiring Soon',
        compute='_compute_dashboard_kpis',
    )

    # Daily Operations
    checkins_today = fields.Integer(
        string="Today's Check-ins",
        compute='_compute_dashboard_kpis',
    )
    classes_today = fields.Integer(
        string="Today's Classes",
        compute='_compute_dashboard_kpis',
    )

    # Management Alerts
    overdue_installments = fields.Integer(
        string='Overdue Installments',
        compute='_compute_dashboard_kpis',
    )
    facilities_attention = fields.Integer(
        string='Facilities Needing Attention',
        compute='_compute_dashboard_kpis',
    )
    open_rehab_files = fields.Integer(
        string='Open Rehabilitation Files',
        compute='_compute_dashboard_kpis',
    )

    @api.depends_context('uid', 'company')
    def _compute_dashboard_kpis(self):
        Membership = self.env['fitzone.membership.subscription']
        Installment = self.env['fitzone.membership.installment']
        Checkin = self.env['fitzone.checkin']
        ClassSchedule = self.env['fitzone.class.schedule']
        Facility = self.env['fitzone.facility']
        RehabFile = self.env['fitzone.rehab.file']
        Payment = self.env['account.payment']

        company = self.env.company
        today = fields.Date.context_today(self)
        start = fields.Datetime.start_of(today, 'day')
        end = fields.Datetime.end_of(today, 'day')
        expiry_limit = today + timedelta(days=7)
        month_start = today.replace(day=1)

        for dashboard in self:
            dashboard.currency_id = company.currency_id

            dashboard.active_memberships = Membership.search_count([
                ('status', '=', 'active'),
            ])

            dashboard.expiring_soon = Membership.search_count([
                ('status', '=', 'active'),
                ('expiration_date', '>=', today),
                ('expiration_date', '<=', expiry_limit),
            ])

            dashboard.checkins_today = Checkin.search_count([
                ('status', '=', 'checked_in'),
                ('checkin_datetime', '>=', start),
                ('checkin_datetime', '<=', end),
            ])

            dashboard.classes_today = ClassSchedule.search_count([
                ('start_datetime', '>=', start),
                ('start_datetime', '<=', end),
            ])

            dashboard.overdue_installments = Installment.search_count([
                ('payment_status', '=', 'overdue'),
            ])

            dashboard.facilities_attention = Facility.search_count([
                ('state', 'in', ['maintenance', 'closed']),
            ])

            dashboard.open_rehab_files = RehabFile.search_count([
                ('state', '=', 'open'),
            ])

            # Outstanding balances on posted membership invoices.
            installments = Installment.search([
                ('invoice_id.state', '=', 'posted'),
                ('invoice_id.move_type', '=', 'out_invoice'),
                ('invoice_id.amount_residual', '>', 0.01),
            ])

            outstanding = 0.0
            for installment in installments:
                invoice = installment.invoice_id
                outstanding += invoice.currency_id._convert(
                    invoice.amount_residual,
                    company.currency_id,
                    company,
                    today,
                )

            dashboard.outstanding_payments = outstanding

            # Count receipts today only when linked to a membership invoice.
            invoices = Installment.search([
                ('invoice_id.state', '=', 'posted'),
                ('invoice_id.move_type', '=', 'out_invoice'),
            ]).mapped('invoice_id')

            payments = Payment.browse()
            if invoices:
                payments = Payment.search([
                    ('company_id', '=', company.id),
                    ('date', '=', today),
                    ('payment_type', '=', 'inbound'),
                    ('state', 'in', ['paid', 'in_process']),
                    ('reconciled_invoice_ids', 'in', invoices.ids),
                ])

            revenue = 0.0
            for payment in payments:
                revenue += payment.currency_id._convert(
                    payment.amount,
                    company.currency_id,
                    company,
                    payment.date,
                )

            dashboard.revenue_today = revenue

            # Membership payments received from the start of this month
            # through today.
            month_payments = Payment.browse()
            if invoices:
                month_payments = Payment.search([
                    ('company_id', '=', company.id),
                    ('date', '>=', month_start),
                    ('date', '<=', today),
                    ('payment_type', '=', 'inbound'),
                    ('state', 'in', ['paid', 'in_process']),
                    ('reconciled_invoice_ids', 'in', invoices.ids),
                ])

            monthly_revenue = 0.0
            for payment in month_payments:
                monthly_revenue += payment.currency_id._convert(
                    payment.amount,
                    company.currency_id,
                    company,
                    payment.date,
                )

            dashboard.revenue_month = monthly_revenue

    # Shared action helpers
    def _open_records(self, title, model, domain):
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': model,
            'view_mode': 'list,form',
            'domain': domain,
        }

    def action_open_revenue_today(self):
        today = fields.Date.context_today(self)
        invoices = self.env[
            'fitzone.membership.installment'
        ].search([
            ('invoice_id.state', '=', 'posted'),
            ('invoice_id.move_type', '=', 'out_invoice'),
        ]).mapped('invoice_id')

        domain = [
            ('company_id', '=', self.env.company.id),
            ('date', '=', today),
            ('payment_type', '=', 'inbound'),
            ('state', 'in', ['paid', 'in_process']),
            ('reconciled_invoice_ids', 'in', invoices.ids),
        ] if invoices else [('id', '=', 0)]

        return self._open_records(
            'Membership Payments Received Today',
            'account.payment',
            domain,
        )

    def action_open_revenue_month(self):
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)

        invoices = self.env[
            'fitzone.membership.installment'
        ].search([
            ('invoice_id.state', '=', 'posted'),
            ('invoice_id.move_type', '=', 'out_invoice'),
        ]).mapped('invoice_id')

        domain = [
            ('company_id', '=', self.env.company.id),
            ('date', '>=', month_start),
            ('date', '<=', today),
            ('payment_type', '=', 'inbound'),
            ('state', 'in', ['paid', 'in_process']),
            ('reconciled_invoice_ids', 'in', invoices.ids),
        ] if invoices else [('id', '=', 0)]

        return self._open_records(
            'Membership Payments Received This Month',
            'account.payment',
            domain,
        )

    def action_open_outstanding_payments(self):
        return self._open_records(
            'Outstanding Membership Invoices',
            'fitzone.membership.installment',
            [
                ('invoice_id.state', '=', 'posted'),
                ('invoice_id.move_type', '=', 'out_invoice'),
                ('invoice_id.amount_residual', '>', 0.01),
            ],
        )

    def action_open_active_memberships(self):
        return self._open_records(
            'Active Memberships',
            'fitzone.membership.subscription',
            [('status', '=', 'active')],
        )

    def action_open_expiring_soon(self):
        today = fields.Date.context_today(self)
        return self._open_records(
            'Memberships Expiring Soon',
            'fitzone.membership.subscription',
            [
                ('status', '=', 'active'),
                ('expiration_date', '>=', today),
                ('expiration_date', '<=', today + timedelta(days=7)),
            ],
        )

    def action_open_checkins_today(self):
        today = fields.Date.context_today(self)
        start = fields.Datetime.start_of(today, 'day')
        end = fields.Datetime.end_of(today, 'day')
        return self._open_records(
            "Today's Check-ins",
            'fitzone.checkin',
            [
                ('status', '=', 'checked_in'),
                ('checkin_datetime', '>=', start),
                ('checkin_datetime', '<=', end),
            ],
        )

    def action_open_classes_today(self):
        today = fields.Date.context_today(self)
        start = fields.Datetime.start_of(today, 'day')
        end = fields.Datetime.end_of(today, 'day')
        return self._open_records(
            "Today's Classes",
            'fitzone.class.schedule',
            [
                ('start_datetime', '>=', start),
                ('start_datetime', '<=', end),
            ],
        )

    def action_open_overdue_installments(self):
        return self._open_records(
            'Overdue Installments',
            'fitzone.membership.installment',
            [('payment_status', '=', 'overdue')],
        )

    def action_open_facilities_attention(self):
        return self._open_records(
            'Facilities Needing Attention',
            'fitzone.facility',
            [('state', 'in', ['maintenance', 'closed'])],
        )

    def action_open_rehab_files(self):
        return self._open_records(
            'Open Rehabilitation Files',
            'fitzone.rehab.file',
            [('state', '=', 'open')],
        )
    def action_open_injury_statistics(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Injury Statistics',
            'res_model': 'fitzone.injury',
            'view_mode': 'graph,list',
            'views': [
                (
                    self.env.ref(
                        'fitzone_management.view_fitzone_injury_cause_graph'
                    ).id,
                    'graph',
                ),
                (False, 'list'),
            ],
        }