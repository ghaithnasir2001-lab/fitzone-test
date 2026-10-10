
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class FitZoneMembershipInstallment(models.Model):
    _name = 'fitzone.membership.installment'
    _description = 'FitZone Membership Installment'
    _order = 'subscription_id, installment_number'

    name = fields.Char(
        string='Installment Reference',
        required=True,
        readonly=True,
        copy=False,
        default='New',
    )

    subscription_id = fields.Many2one(
        'fitzone.membership.subscription',
        string='Membership Subscription',
        required=True,
        ondelete='restrict',
    )

    installment_number = fields.Selection(
        [
            ('1', 'First Installment'),
            ('2', 'Second Installment'),
        ],
        string='Installment',
        required=True,
    )

    currency_id = fields.Many2one(
        related='subscription_id.currency_id',
        string='Currency',
        readonly=True,
    )

    amount = fields.Monetary(
        string='Installment Amount',
        currency_field='currency_id',
        required=True,
    )

    due_date = fields.Date(
        string='Due Date',
        required=True,
    )

    payment_method = fields.Selection(
        [
            ('cash', 'Cash'),
            ('card', 'Card'),
            ('e_wallet', 'E-Wallet'),
        ],
        string='Expected Payment Method',
        required=True,
        default='cash',
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Customer Invoice',
        readonly=True,
        copy=False,
        ondelete='restrict',
    )

    invoice_state = fields.Selection(
        related='invoice_id.state',
        string='Invoice Status',
        readonly=True,
    )

    amount_paid = fields.Monetary(
        string='Amount Paid',
        currency_field='currency_id',
        compute='_compute_payment_amounts',
    )

    amount_due = fields.Monetary(
        string='Outstanding Amount',
        currency_field='currency_id',
        compute='_compute_payment_amounts',
    )

    payment_status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
        ],
        string='Payment Status',
        compute='_compute_payment_status',
        store=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code(
                        'fitzone.membership.installment'
                    )
                    or 'New'
                )
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(
                    'Installment amount must be greater than zero.'
                )

    @api.constrains('subscription_id', 'installment_number')
    def _check_unique_installment_number(self):
        for record in self:
            duplicate = self.search_count([
                ('id', '!=', record.id),
                ('subscription_id', '=', record.subscription_id.id),
                ('installment_number', '=', record.installment_number),
            ])
            if duplicate:
                raise ValidationError(
                    'This installment already exists for the subscription.'
                )

    @api.depends(
        'amount',
        'invoice_id.amount_residual',
        'invoice_id.amount_total',
        'invoice_id.state',
    )
    def _compute_payment_amounts(self):
        for record in self:
            invoice = record.invoice_id

            if invoice and invoice.state == 'posted':
                record.amount_due = invoice.amount_residual
                record.amount_paid = max(
                    invoice.amount_total - invoice.amount_residual,
                    0.0,
                )
            else:
                record.amount_paid = 0.0
                record.amount_due = record.amount

    @api.depends(
        'due_date',
        'invoice_id.state',
        'invoice_id.amount_residual',
    )
    def _compute_payment_status(self):
        today = fields.Date.context_today(self)

        for record in self:
            invoice = record.invoice_id

            if (
                invoice
                and invoice.state == 'posted'
                and invoice.amount_residual <= 0.01
            ):
                record.payment_status = 'paid'
            elif record.due_date and record.due_date < today:
                record.payment_status = 'overdue'
            else:
                record.payment_status = 'pending'

    def action_create_invoice(self):
        """Create and post an official Odoo customer invoice."""
        for record in self:
            if record.invoice_id:
                raise UserError(
                    'An invoice already exists for this installment.'
                )

            company = self.env.company
            subscription = record.subscription_id

            if not subscription.subscriber_id:
                raise UserError(
                    'Set the subscriber before creating an invoice.'
                )

            if not company.currency_id:
                raise UserError(
                    'Configure the company currency before invoicing.'
                )

            income_account = self.env['account.account'].search([
                ('company_ids', 'in', [company.id]),
                ('account_type', 'in', ['income', 'income_other']),
            ], limit=1)

            if not income_account:
                raise UserError(
                    'No income account was found. Configure the chart '
                    'of accounts before creating invoices.'
                )

            tax = self.env['account.tax'].search([
                ('company_id', '=', company.id),
                ('type_tax_use', '=', 'sale'),
                ('amount', '=', 16.0),
                ('active', '=', True),
            ], limit=1)

            if not tax:
                raise UserError(
                    'Configure the 16% sales tax as price-included in '
                    'Odoo Accounting before creating membership invoices.'
                )

            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': subscription.subscriber_id.id,
                'company_id': company.id,
                'invoice_date': fields.Date.context_today(record),
                'invoice_date_due': record.due_date,
                'invoice_line_ids': [
                    fields.Command.create({
                        'name': (
                            f'{subscription.name} - '
                            f'Installment {record.installment_number}'
                        ),
                        'quantity': 1.0,
                        'price_unit': record.amount / 1.16,
                        'account_id': income_account.id,
                        'tax_ids': [fields.Command.set([tax.id])],
                    }),
                ],
            })

            invoice.action_post()
            record.invoice_id = invoice

        return True