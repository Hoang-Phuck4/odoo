from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    dob = fields.Date('Ngày sinh', required=True)
    gender = fields.Selection([('male','Nam'),('female','Nữ'),('other','Khác')], 'Giới tính')
    identity_id = fields.Char('CCCD', required=True)
    identity_place = fields.Char('Nơi cấp CCCD')
    identity_date = fields.Date('Ngày cấp CCCD')
    identity_expiry = fields.Date('Ngày hết hạn CCCD')
    nationality = fields.Char('Quốc tịch')
    ethnicity = fields.Char('Dân tộc')
    religion = fields.Char('Tôn giáo')
    work_email = fields.Char('Email công việc', required=True)
    work_phone = fields.Char('Số điện thoại', required=True)

    # Sửa job_title sang Char để tránh lỗi liên quan res.users
    job_title = fields.Char('Chức vụ công tác')

    department_id = fields.Many2one('hr.department', 'Phòng ban')
    contract_type = fields.Many2one('employee.type', 'Loại nhân viên', required=True)
    degree_id = fields.Many2one('degree', 'Trình độ')
    current_contract = fields.Char('Hợp đồng hiện hành')
    major = fields.Char('Chuyên ngành')
    bank_name = fields.Char('Tên ngân hàng')
    bank_account = fields.Char('Tài khoản NH')
    bank_branch = fields.Char('Chi nhánh')
    beneficiary = fields.Char('Người thụ hưởng')
    tax_code = fields.Char('Mã số thuế')
    status_id = fields.Many2one('employee.status', 'Trạng thái')

    # Thêm field address
    address = fields.Char('Địa chỉ')

    @api.constrains('name', 'work_email', 'work_phone', 'identity_id', 'dob', 'contract_type')
    def _check_required_fields(self):
        for rec in self:
            missing = []
            if not rec.name:
                missing.append('Họ tên')
            if not rec.work_email:
                missing.append('Email công việc')
            if not rec.work_phone:
                missing.append('Số điện thoại')
            if not rec.identity_id:
                missing.append('CCCD')
            if not rec.dob:
                missing.append('Ngày sinh')
            if not rec.contract_type:
                missing.append('Loại nhân viên')
            if missing:
                raise ValidationError(f"Các trường bắt buộc không được để trống: {', '.join(missing)}")
