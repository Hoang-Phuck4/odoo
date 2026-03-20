from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta

# ====================== LOẠI NGHỈ PHÉP ======================
class EmployeeLeaveType(models.Model):
    _name = "employee.leave.type"
    _description = "Loại nghỉ phép"

    name = fields.Char(string="Tên loại nghỉ phép", required=True)
    code = fields.Char(string="Mã loại", required=True)
    default_days = fields.Float(string="Số ngày mặc định/năm", default=12.0)
    allow_advance = fields.Boolean(string="Cho phép nghỉ ứng trước", default=False)
    is_public_holiday = fields.Boolean(string="Ngày lễ công ty", default=False)


# ====================== ĐƠN NGHỈ PHÉP ======================
class EmployeeLeaveRequest(models.Model):
    _name = "employee.leave.request"
    _description = "Đơn nghỉ phép / Giải trình"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one("hr.employee", string="Nhân sự", required=True, tracking=True)
    leave_type_id = fields.Many2one("employee.leave.type", string="Loại nghỉ phép", required=True, tracking=True)
    start_date = fields.Date(string="Ngày bắt đầu", required=True, tracking=True)
    end_date = fields.Date(string="Ngày kết thúc", required=True, tracking=True)
    leave_days = fields.Float(string="Số ngày nghỉ", compute="_compute_leave_days", store=True)
    reason = fields.Text(string="Lý do nghỉ", tracking=True)
    status = fields.Selection([
        ("draft", "Nháp"),
        ("to_approve", "Chờ duyệt"),
        ("manager_approved", "Trưởng đơn vị duyệt"),
        ("hr_approved", "P.TC-HC/Hiệu trưởng duyệt"),
        ("done", "Hoàn thành"),
        ("refused", "Từ chối"),
    ], string="Trạng thái", default="draft", tracking=True)

    name = fields.Char(string="Tên nhân viên", compute="_compute_name", store=True)
    remaining_days = fields.Float(string="Số ngày còn lại", compute="_compute_remaining_days", store=True)

    @api.depends("employee_id")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.employee_id.name if rec.employee_id else "Unknown"

    @api.depends("start_date", "end_date")
    def _compute_leave_days(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date >= rec.start_date:
                rec.leave_days = (rec.end_date - rec.start_date).days + 1
            else:
                rec.leave_days = 0

    @api.depends("employee_id", "leave_type_id")
    def _compute_remaining_days(self):
        for rec in self:
            if rec.employee_id and rec.leave_type_id:
                leave_records = self.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('leave_type_id', '=', rec.leave_type_id.id),
                    ('status', 'in', ['done', 'hr_approved', 'manager_approved'])
                ])
                used_days = sum(r.leave_days for r in leave_records)
                rec.remaining_days = rec.leave_type_id.default_days - used_days
            else:
                rec.remaining_days = 0

    # ================= Action workflow =================
    def action_submit(self):
        """Nhân viên gửi duyệt"""
        for rec in self:
            # Kiểm tra số ngày nghỉ hợp lệ
            if not rec.leave_type_id.allow_advance and rec.leave_days > rec.remaining_days:
                raise ValidationError(_(
                    "Số ngày nghỉ (%s) vượt quá số ngày còn lại (%s) cho loại nghỉ phép '%s'. "
                    "Bạn không thể gửi duyệt."
                ) % (rec.leave_days, rec.remaining_days, rec.leave_type_id.name))

        self.write({"status": "to_approve"})

    def action_manager_approve(self):
        self.write({"status": "manager_approved"})

    def action_hr_approve(self):
        self.write({"status": "hr_approved"})

    def action_done(self):
        self.write({"status": "done"})

    def action_refuse(self):
        self.write({"status": "refused"})
