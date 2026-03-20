from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Mã nhân viên sẽ là login
    login = fields.Char(
        string='Mã nhân viên',
        required=True,
        index=True,
        help="Nhập mã nhân viên để đăng nhập"
    )

    # Liên kết nhân viên
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', readonly=True)

    # Nhập mật khẩu chưa hash
    plain_password = fields.Char(
        string="Mật khẩu",
        store=False,
        help="Nhập mật khẩu khi tạo User (sẽ được hash tự động)."
    )

    def _validate_password_strength(self, password):
        if len(password) < 8:
            raise ValidationError(_("Mật khẩu phải có ít nhất 8 ký tự."))
        if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise ValidationError(_("Mật khẩu phải bao gồm cả chữ cái và số."))

    @api.model
    def create(self, vals):
        # Nếu nhập employee_code mà chưa gán employee_id, tìm nhân viên tương ứng
        if 'login' in vals and not vals.get('employee_id'):
            emp = self.env['hr.employee'].search([('employee_code', '=', vals['login'])], limit=1)
            if emp:
                vals['employee_id'] = emp.id

        # Hash mật khẩu nếu có plain_password
        if vals.get('plain_password'):
            self._validate_password_strength(vals['plain_password'])
            vals['password'] = vals.pop('plain_password')

        return super().create(vals)

    def write(self, vals):
        # Hash mật khẩu nếu có plain_password
        if vals.get('plain_password'):
            self._validate_password_strength(vals['plain_password'])
            vals['password'] = vals.pop('plain_password')
        return super().write(vals)
