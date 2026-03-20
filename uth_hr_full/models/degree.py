from odoo import models, fields

class Degree(models.Model):
    _name = 'degree'
    _description = 'Học hàm / Học vị'

    name = fields.Char('Tên', required=True)
