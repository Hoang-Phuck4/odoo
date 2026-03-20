from odoo import models, fields

class EmployeeType(models.Model):
    _name = 'employee.type'
    _description = 'Loại nhân viên'

    name = fields.Char('Tên loại nhân viên', required=True)
    code = fields.Char('Mã', required=True)
