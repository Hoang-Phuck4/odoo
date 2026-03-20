from odoo import models, fields

class EmployeeStatus(models.Model):
    _name = 'employee.status'
    _description = 'Trạng thái nhân viên'

    name = fields.Char('Tên trạng thái', required=True)
    code = fields.Char('Mã', required=True)
