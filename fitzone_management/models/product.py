from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    fitzone_kind = fields.Selection(
        [
            ('service', 'Service'),
            ('package', 'Membership Package'),
            ('retail', 'Retail Product'),
        ],
        string='FitZone Kind',
        default='service',
        required=True,
    )

    product_type = fields.Selection(
        [
            ('health', 'Health Product'),
            ('supplement', 'Supplement'),
            ('juice', 'Juice'),
            ('snack', 'Snack'),
        ],
        string='Retail Product Type',
    )

    @api.onchange('product_type')
    def _onchange_product_type(self):
        for product in self:
            product._apply_fitzone_retail_configuration()

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        products._apply_fitzone_retail_configuration()
        return products

    def write(self, vals):
        result = super().write(vals)
        if 'product_type' in vals:
            self._apply_fitzone_retail_configuration()
        return result

    def _apply_fitzone_retail_configuration(self):
        for product in self:
            if product.fitzone_kind != 'retail':
                continue

            if product.product_type in ('health', 'supplement'):
                product.is_storable = True
                product.tracking = 'lot'
                product.use_expiration_date = True
            elif product.product_type in ('juice', 'snack'):
                product.is_storable = False
                product.tracking = 'none'
                product.use_expiration_date = False
