# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, time, timedelta
import calendar
import io
import csv
import base64
import logging

_logger = logging.getLogger(__name__)

# =======================
# Employee Attendance App
# - EmployeeAttendanceCustom: lưu chấm công hằng ngày
# - AttendanceCheckWizard: wizard check-in / check-out
# - EmployeeAttendanceReport: báo cáo tháng
# - AttendanceReportWizard: wizard sinh báo cáo
#
# Quy ước:
# - Loại công chỉ còn 2: 'normal' và 'contract'
# - 'contract' phụ thuộc vào uth.contract.is_khoan
# =======================


class EmployeeAttendanceCustom(models.Model):
    _name = "employee.attendance.custom"
    _description = "Chấm công nhân sự"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date desc, employee_id"

    # ================= FIELDS =================
    employee_id = fields.Many2one('hr.employee', string="Nhân sự", required=True, tracking=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban",
                                    related="employee_id.department_id", store=True)
    date = fields.Date(string="Ngày công", default=fields.Date.context_today, tracking=True)
    check_in = fields.Datetime(string="Giờ vào", tracking=True)
    check_out = fields.Datetime(string="Giờ ra", tracking=True)

    # Hợp đồng hiện tại của nhân viên (tự động lấy hợp đồng 'running' mới nhất)
    current_contract_id = fields.Many2one('uth.contract', string='Hợp đồng hiện tại',
                                          compute='_compute_current_contract', store=True)
    # Lịch làm việc (lấy từ contract.calendar_id)
    calendar_id = fields.Many2one('resource.calendar', string='Lịch làm việc',
                                  compute='_compute_calendar_from_contract', store=True)
    # Giờ dự kiến (computed từ resource.calendar.attendance)
    expected_start = fields.Datetime(string="Giờ vào dự kiến", compute='_compute_expected_times', store=True)
    expected_end = fields.Datetime(string="Giờ ra dự kiến", compute='_compute_expected_times', store=True)

    # Loại công: chỉ còn 2 loại -> 'normal' hoặc 'contract'
    work_type = fields.Selection([
        ('normal', 'Công bình thường'),
        ('contract', 'Hợp đồng khoán')
    ], string="Loại công", compute='_compute_work_type', store=True, tracking=True)

    work_hours = fields.Float(string="Số giờ làm việc", compute="_compute_work_hours", store=True)
    work_hours_display = fields.Char(string="Giờ làm việc (hh:mm)", compute="_compute_work_hours_display")
    overtime = fields.Float(string="OT (giờ)", compute="_compute_overtime", store=True)
    leave_days = fields.Float(string="Ngày phép", compute="_compute_leave_days", store=True)

    note = fields.Text(string="Giải trình")
    status = fields.Selection([('draft', 'Chưa check in'),
                               ('confirmed', 'Đã check in'),
                               ('approved', 'Đã check out')],
                              string="Trạng thái", default='draft', tracking=True)
    approval_status = fields.Selection([('draft', 'Gửi Duyệt OT'),
                                        ('submitted', 'Đã gửi duyệt'),
                                        ('waiting', 'Chờ duyệt'),
                                        ('accepted', 'Chấp nhận OT'),
                                        ('refused', 'Từ chối OT')],
                                       string="Duyệt OT", default='draft', tracking=True)

    display_status = fields.Selection([('attended', 'Đã chấm'),
                                       ('not_attended', 'Chưa chấm'),
                                       ('on_leave', 'Ngày phép')],
                                      string="Trạng thái hiển thị", compute="_compute_display_status", store=True)

    can_submit_overtime = fields.Boolean(string="Can Submit OT", compute="_compute_can_submit_overtime")
    name = fields.Char(string="Tên nhân viên", compute="_compute_name", store=True)

    # Dạng chuỗi hiển thị ca hôm nay
    timetable = fields.Char(string="Ca làm", compute="_compute_timetable", store=True)
    # Dữ liệu ca cho cả tháng (JSON-like list)
    timetable_month = fields.Json(string="Ca tháng", compute="_compute_month_timetable")

    # ================ SQL Constraint ================
    _sql_constraints = [
        ('unique_employee_date', 'unique(employee_id, date)',
         'Nhân viên chỉ được chấm công 1 lần mỗi ngày!')
    ]

    # ================== COMPUTE METHODS ==================

    @api.depends('employee_id')
    def _compute_name(self):
        """Compute display name from employee"""
        for rec in self:
            rec.name = rec.employee_id.name if rec.employee_id else "Unknown"

    @api.depends('employee_id')
    def _compute_current_contract(self):
        """Lấy hợp đồng đang chạy mới nhất của nhân viên"""
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.employee_id:
                rec.current_contract_id = False
                continue
            contract = self.env['uth.contract'].sudo().search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'running'),
                '|', ('end_date', '=', False), ('end_date', '>=', today)
            ], order='start_date desc', limit=1)
            rec.current_contract_id = contract or False

    @api.depends('current_contract_id')
    def _compute_calendar_from_contract(self):
        """Lấy calendar từ contract"""
        for rec in self:
            rec.calendar_id = rec.current_contract_id.calendar_id if rec.current_contract_id else False

    @staticmethod
    def float_to_time(hour_float):
        """Chuyển float (ví dụ 7.5) -> time(7,30)"""
        h = int(hour_float)
        m = int(round((hour_float - h) * 60))
        return time(hour=h, minute=m)

    @api.depends('calendar_id', 'date')
    def _compute_expected_times(self):
        """Tính start/end dự kiến dựa vào resource.calendar.attendance"""
        for rec in self:
            rec.expected_start = None
            rec.expected_end = None
            if rec.calendar_id and rec.date:
                dayofweek = str(rec.date.weekday())
                attendances = self.env['resource.calendar.attendance'].sudo().search([
                    ('calendar_id', '=', rec.calendar_id.id),
                    ('dayofweek', '=', dayofweek)
                ], order='hour_from')
                if attendances:
                    rec.expected_start = datetime.combine(rec.date, self.float_to_time(attendances[0].hour_from))
                    rec.expected_end = datetime.combine(rec.date, self.float_to_time(attendances[-1].hour_to))

    @api.depends('calendar_id', 'date')
    def _compute_timetable(self):
        """Chuỗi hiển thị ca hôm nay (ví dụ '07:30 - 11:30, 13:00 - 17:00')"""
        for rec in self:
            if not rec.calendar_id or not rec.date:
                rec.timetable = 'Không có ca hôm nay'
                continue
            dayofweek = str(rec.date.weekday())
            attendances = self.env['resource.calendar.attendance'].sudo().search([
                ('calendar_id', '=', rec.calendar_id.id),
                ('dayofweek', '=', dayofweek)
            ], order='hour_from')
            if not attendances:
                rec.timetable = 'Không có ca hôm nay'
                continue
            slots = []
            for att in attendances:
                h_from = int(att.hour_from)
                m_from = int(round((att.hour_from - h_from) * 60))
                h_to = int(att.hour_to)
                m_to = int(round((att.hour_to - h_to) * 60))
                slots.append(f"{h_from:02d}:{m_from:02d} - {h_to:02d}:{m_to:02d}")
            rec.timetable = ', '.join(slots)

    @api.depends('calendar_id', 'date')
    def _compute_month_timetable(self):
        """Tạo timetable cho cả tháng (dùng để hiển thị lịch)"""
        for rec in self:
            rec.timetable_month = []
            if not rec.calendar_id or not rec.date:
                continue
            start_month = rec.date.replace(day=1)
            last_day = calendar.monthrange(rec.date.year, rec.date.month)[1]
            for day in range(1, last_day + 1):
                day_date = start_month.replace(day=day)
                day_of_week = day_date.weekday()
                attendances = self.env['resource.calendar.attendance'].sudo().search([
                    ('calendar_id', '=', rec.calendar_id.id),
                    ('dayofweek', '=', str(day_of_week))
                ], order='hour_from')
                slots = []
                for att in attendances:
                    h_from, m_from = int(att.hour_from), int(round((att.hour_from - int(att.hour_from)) * 60))
                    h_to, m_to = int(att.hour_to), int(round((att.hour_to - int(att.hour_to)) * 60))
                    slots.append(f"{h_from:02d}:{m_from:02d}-{h_to:02d}:{m_to:02d}")
                # Kiểm tra nếu đã có chấm công ngày đó
                attendance_record = self.env['employee.attendance.custom'].sudo().search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('date', '=', day_date)
                ], limit=1)
                status = 'not_attended'
                if attendance_record:
                    if attendance_record.leave_days > 0:
                        status = 'on_leave'
                    elif attendance_record.check_in:
                        status = 'attended'
                rec.timetable_month.append({
                    'date': day_date,
                    'slots': ', '.join(slots) if slots else 'Không có ca hôm nay',
                    'status': status
                })

    @api.depends('current_contract_id')
    def _compute_work_type(self):
        """Đồng bộ loại công theo hợp đồng hiện tại (dựa vào is_khoan trong contract)"""
        for rec in self:
            contract = rec.current_contract_id
            if not contract:
                rec.work_type = False
            elif getattr(contract, 'is_khoan', False):
                rec.work_type = 'contract'
            else:
                rec.work_type = 'normal'

    @api.depends('date', 'employee_id')
    def _compute_leave_days(self):
        """Tính xem ngày hiện tại có phải nằm trong leave request hay không"""
        for rec in self:
            if not rec.employee_id:
                rec.leave_days = 0.0
                continue
            leaves = self.env['employee.leave.request'].sudo().search([
                ('employee_id', '=', rec.employee_id.id),
                ('status', 'in', ['done', 'manager_approved', 'hr_approved']),
                ('start_date', '<=', rec.date),
                ('end_date', '>=', rec.date)
            ])
            if not leaves:
                rec.leave_days = 0.0
            else:
                # nếu có nhiều leave chồng lên, tính tổng ngày trong ngày này (đại khái 1)
                rec.leave_days = sum(
                    min((rec.date - l.start_date).days + 1, (l.end_date - l.start_date).days + 1) for l in leaves
                )

    @api.depends('check_in', 'check_out', 'leave_days')
    def _compute_work_hours(self):
        """Tính giờ làm thực tế, không giới hạn expected_start/end"""
        for rec in self:
            if rec.leave_days > 0 or not rec.check_in or not rec.check_out:
                rec.work_hours = 0.0
            else:
                diff = rec.check_out - rec.check_in
                rec.work_hours = round(diff.total_seconds() / 3600, 2)

    @api.depends('work_hours', 'work_type')
    def _compute_overtime(self):
        """OT = work_hours - 8 nếu là công bình thường"""
        for rec in self:
            rec.overtime = max(0.0, rec.work_hours - 8.0) if rec.work_type == 'normal' else 0.0


    @api.depends('check_in', 'check_out', 'leave_days')
    def _compute_work_hours_display(self):
        """Chuỗi hiển thị giờ làm (hh:mm) dựa vào check_in/check_out"""
        for rec in self:
            if rec.leave_days > 0:
                rec.work_hours_display = "0:00"
            elif rec.check_in and rec.check_out:
                diff = rec.check_out - rec.check_in
                hours, remainder = divmod(int(diff.total_seconds()), 3600)
                minutes = remainder // 60
                rec.work_hours_display = f"{hours}:{minutes:02d}"
            else:
                rec.work_hours_display = "0:00"

    @api.depends('overtime', 'approval_status')
    def _compute_can_submit_overtime(self):
        for rec in self:
            rec.can_submit_overtime = rec.overtime > 0 and rec.approval_status == 'draft'

    @api.depends('check_in', 'check_out', 'leave_days')
    def _compute_display_status(self):
        today = date.today()
        for rec in self:
            if rec.leave_days > 0:
                rec.display_status = 'on_leave'
            elif rec.date == today and rec.check_in:
                rec.display_status = 'attended'
            else:
                rec.display_status = 'not_attended'

    # ================== ACTIONS ==================
    def action_submit_overtime(self):
        for rec in self:
            if rec.overtime <= 0:
                raise UserError(_("Không có OT để gửi duyệt."))
            rec.sudo().write({'approval_status': 'waiting'})
        return True

    def _action_open_check_wizard(self, check_type):
        """Mở wizard để chọn thời gian check-in/check-out (dùng view transient)"""
        self.ensure_one()
        today = self.date
        employee = self.employee_id
        existing_records = self.env['employee.attendance.custom'].sudo().search([
            ('employee_id', '=', employee.id),
            ('date', '=', today)
        ])
        if check_type == 'in' and existing_records.filtered(lambda r: r.check_in):
            raise UserError(_("Nhân viên %s đã check-in hôm nay." % employee.name))
        if check_type == 'out':
            if not self.check_in:
                raise UserError(_("Nhân viên %s chưa check-in hôm nay nên không thể check-out." % employee.name))
            if existing_records.filtered(lambda r: r.check_out):
                raise UserError(_("Nhân viên %s đã check-out hôm nay." % employee.name))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Chọn thời gian"),
            'res_model': 'attendance.check.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_attendance_id': self.id,
                'default_employee_id': self.employee_id.id,
                'default_check_type': check_type,
                'default_check_datetime': fields.Datetime.now(),
            }
        }

    def action_open_checkin_wizard(self):
        return self._action_open_check_wizard('in')

    def action_open_checkout_wizard(self):
        return self._action_open_check_wizard('out')

    def action_accept_overtime(self):
        self.sudo().write({'approval_status': 'accepted'})

    def action_refuse_overtime(self):
        self.sudo().write({'approval_status': 'refused'})

    # ================== HELPERS / BATCH OPERATIONS ==================
    @api.model
    def cron_fill_missing_attendance(self):
        """
        Cron job helper (gợi ý): tạo bản ghi chấm công rỗng cho các nhân viên có hợp đồng running
        trong khoảng thời gian nhất định nếu bạn muốn có bản ghi để xem lịch tháng.
        Lưu ý: dùng cẩn thận, tránh tạo quá nhiều bản ghi không cần thiết.
        """
        today = fields.Date.context_today(self)
        employees = self.env['hr.employee'].sudo().search([])
        created = 0
        for emp in employees:
            # nếu đã có record cho hôm nay thì skip
            exists = self.search([('employee_id', '=', emp.id), ('date', '=', today)], limit=1)
            if exists:
                continue
            # Kiểm tra hợp đồng running
            contract = self.env['uth.contract'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'running'),
                '|', ('end_date', '=', False), ('end_date', '>=', today)
            ], limit=1)
            if not contract:
                continue
            self.sudo().create({
                'employee_id': emp.id,
                'date': today,
            })
            created += 1
        _logger.info("cron_fill_missing_attendance created %s attendance records", created)
        return True


# ================= WIZARD FOR CHECK IN / CHECK OUT =================
class AttendanceCheckWizard(models.TransientModel):
    _name = "attendance.check.wizard"
    _description = "Wizard chọn thời gian Check In/Out"

    attendance_id = fields.Many2one('employee.attendance.custom', string="Bản ghi chấm công", required=True)
    employee_id = fields.Many2one('hr.employee', string="Nhân sự", required=True)
    check_type = fields.Selection([('in', 'Check In'), ('out', 'Check Out')], string="Loại", required=True)
    check_datetime = fields.Datetime(string="Thời gian", required=True, default=lambda self: fields.Datetime.now())
    note = fields.Char(string="Ghi chú")

    def action_confirm(self):
        """
        Xử lý check in / check out:
         - Kiểm tra hợp đồng hiện tại đang run
         - Kiểm tra ngày nghỉ
         - Kiểm tra ca làm
         - Ghi check_in / check_out vào attendance record
        """
        self.ensure_one()
        rec = self.attendance_id
        dt = self.check_datetime or fields.Datetime.now()

        # ===== KIỂM TRA HỢP ĐỒNG =====
        contract = rec.current_contract_id
        today = fields.Date.context_today(self)
        if not contract or contract.state != 'running' or (contract.end_date and contract.end_date < today):
            raise UserError(_("Nhân viên không có hợp đồng đang chạy, không thể chấm công."))

        # ===== KIỂM TRA NGÀY NGHỈ =====
        if rec.leave_days > 0:
            raise UserError(_("Hôm nay là ngày nghỉ phép, không thể chấm công."))

        # ===== KIỂM TRA CA LÀM (nếu cần) =====
        if not rec.calendar_id:
            raise UserError(_("Hôm nay nhân viên không có ca làm việc, không thể chấm công."))

        dayofweek = str(rec.date.weekday())
        attendances = self.env['resource.calendar.attendance'].sudo().search([
            ('calendar_id', '=', rec.calendar_id.id),
            ('dayofweek', '=', dayofweek)
        ])
        if not attendances:
            raise UserError(_("Hôm nay nhân viên không có ca làm việc, không thể chấm công."))

        local_dt = fields.Datetime.context_timestamp(self.env.user, dt)

        # ===== CHECK IN =====
        if self.check_type == 'in':
            if rec.check_in:
                raise UserError(_("Bản ghi đã có Check In."))
            note_extra = "\n[Giải trình] Check-in sau 7:30" if local_dt.time() > time(7, 30) else ""
            rec.sudo().write({
                'check_in': dt,
                'status': 'confirmed',
                'note': (rec.note or '') + (f"\n[Check In wizard] {self.note}" if self.note else '') + note_extra
            })
        else:
            # CHECK OUT
            if not rec.check_in:
                raise UserError(_("Chưa có Check In để Check Out."))
            if rec.check_out:
                raise UserError(_("Bản ghi đã có Check Out."))
            if dt < rec.check_in:
                raise ValidationError(_("Thời điểm Check Out phải >= Check In."))
            note_extra = "\n[Giải trình] Check-out trước 16:30" if local_dt.time() < time(16, 30) else ""
            rec.sudo().write({
                'check_out': dt,
                'status': 'approved',
                'note': (rec.note or '') + (f"\n[Check Out wizard] {self.note}" if self.note else '') + note_extra
            })

        return {'type': 'ir.actions.act_window_close'}


# ================= EMPLOYEE ATTENDANCE REPORT =================
class EmployeeAttendanceReport(models.Model):
    _name = "employee.attendance.report"
    _description = "Báo cáo chấm công nhân sự"
    _rec_name = "employee_id"

    employee_id = fields.Many2one('hr.employee', string="Nhân viên", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban",
                                    related="employee_id.department_id", store=True)
    month = fields.Selection([(str(i), str(i)) for i in range(1, 13)], string="Tháng", required=True)
    year = fields.Selection([(str(y), str(y)) for y in range(2020, datetime.now().year + 6)], string="Năm", required=True)

    total_work_hours = fields.Float(string="Tổng giờ làm việc", compute="_compute_totals", store=True)
    total_overtime = fields.Float(string="Tổng OT", compute="_compute_totals", store=True)
    total_leave_days = fields.Float(string="Tổng ngày nghỉ", compute="_compute_totals", store=True)
    total_work_hours_with_ot = fields.Float(string="Tổng giờ làm + OT", compute="_compute_totals", store=True)

    # Choose to export CSV
    report_file = fields.Binary(string="CSV Report (Base64)")
    report_file_name = fields.Char(string="Filename")

    @api.depends('employee_id', 'month', 'year')
    def _compute_totals(self):
        """Tính tổng giờ, OT, ngày nghỉ cho tháng được chọn"""
        for rec in self:
            if not rec.employee_id or not rec.month or not rec.year:
                rec.total_work_hours = rec.total_overtime = rec.total_leave_days = rec.total_work_hours_with_ot = 0.0
                continue
            start_date = date(int(rec.year), int(rec.month), 1)
            last_day = calendar.monthrange(int(rec.year), int(rec.month))[1]
            end_date = date(int(rec.year), int(rec.month), last_day)

            attendances = self.env['employee.attendance.custom'].sudo().search([
                ('employee_id', '=', rec.employee_id.id),
                ('date', '>=', start_date),
                ('date', '<=', end_date)
            ])
            # Tổng giờ bình thường: giới hạn 8h/ngày
            rec.total_work_hours = sum(min(att.work_hours, 8) for att in attendances)
            # Chỉ tính OT nếu approved/accepted
            rec.total_overtime = sum(att.overtime for att in attendances if att.approval_status == 'accepted')

            # Tính ngày nghỉ
            leaves = self.env['employee.leave.request'].sudo().search([
                ('employee_id', '=', rec.employee_id.id),
                ('status', 'in', ['done', 'manager_approved', 'hr_approved']),
                ('start_date', '<=', end_date),
                ('end_date', '>=', start_date),
            ])
            total_leave_days = 0.0
            for l in leaves:
                leave_start = max(l.start_date, start_date)
                leave_end = min(l.end_date, end_date)
                total_leave_days += (leave_end - leave_start).days + 1
            rec.total_leave_days = total_leave_days

            rec.total_work_hours_with_ot = rec.total_work_hours + rec.total_overtime

    # ================ EXPORT CSV for report ================
    def action_export_csv(self):
        """Xuất báo cáo thành CSV (Base64) và attach vào record để user tải xuống."""
        for rec in self:
            # Recompute totals to ensure up-to-date
            rec._compute_totals()
            start_date = date(int(rec.year), int(rec.month), 1)
            last_day = calendar.monthrange(int(rec.year), int(rec.month))[1]
            end_date = date(int(rec.year), int(rec.month), last_day)

            attendances = self.env['employee.attendance.custom'].sudo().search([
                ('employee_id', '=', rec.employee_id.id),
                ('date', '>=', start_date),
                ('date', '<=', end_date)
            ], order='date asc')

            # Prepare CSV stream
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            # Header
            writer.writerow([
                'Employee', 'Department', 'Date', 'Check In', 'Check Out',
                'Work Hours', 'OT Hours', 'Work Type', 'Approval Status', 'Note'
            ])
            for att in attendances:
                writer.writerow([
                    att.employee_id.name or '',
                    att.department_id.name or '',
                    att.date.isoformat() if att.date else '',
                    fields.Datetime.to_string(att.check_in) if att.check_in else '',
                    fields.Datetime.to_string(att.check_out) if att.check_out else '',
                    '{:.2f}'.format(att.work_hours) if att.work_hours is not None else '',
                    '{:.2f}'.format(att.overtime) if att.overtime is not None else '',
                    att.work_type or '',
                    att.approval_status or '',
                    att.note or ''
                ])
            csv_data = buffer.getvalue().encode('utf-8')
            buffer.close()

            b64 = base64.b64encode(csv_data)
            filename = "attendance_report_%s_%s_%s.csv" % (rec.employee_id.name.replace(' ', '_'), rec.year, rec.month)
            rec.report_file = b64
            rec.report_file_name = filename

        # return action to download (open record form is sufficient; user can click attachment)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'employee.attendance.report',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new'
        }

    def action_update_report(self):
        """Force recompute totals for the recordset"""
        for rec in self:
            rec._compute_totals()
        return True


# ================= WIZARD TẠO BÁO CÁO =================
class AttendanceReportWizard(models.TransientModel):
    _name = "attendance.report.wizard"
    _description = "Wizard tạo báo cáo chấm công"

    month = fields.Selection([(str(i), str(i)) for i in range(1, 13)], string="Tháng", required=True)
    year = fields.Selection([(str(y), str(y)) for y in range(2020, datetime.now().year + 6)], string="Năm", required=True)

    def action_generate_report(self):
        """Sinh report cho tất cả nhân viên (xóa report cũ của họ rồi tạo mới)"""
        if not self.month or not self.year:
            raise UserError(_("Bạn phải chọn tháng và năm để tạo báo cáo."))

        employees = self.env['hr.employee'].sudo().search([])
        for emp in employees:
            # Xoá báo cáo cũ (nếu có) cho employee
            old_reports = self.env['employee.attendance.report'].sudo().search([
                ('employee_id', '=', emp.id),
                ('month', '=', self.month),
                ('year', '=', self.year)
            ])
            if old_reports:
                old_reports.sudo().unlink()

            report = self.env['employee.attendance.report'].sudo().create({
                'employee_id': emp.id,
                'month': self.month,
                'year': self.year
            })
            # Tính toán ngay
            report._compute_totals()

        # reload client
        return {'type': 'ir.actions.client', 'tag': 'reload'}
