# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, datetime
import calendar
import logging
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

# ==================== HẰNG SỐ ====================
PERSONAL_DEDUCTION = 11000000        # Giảm trừ bản thân
DEPENDENT_DEDUCTION = 4400000        # Giảm trừ người phụ thuộc
EMPLOYEE_SI_RATE = 0.105             # % NLĐ đóng BHXH
COMPANY_SI_RATE = 0.215              # % DN đóng BHXH
BIRTHDAY_GIFT = 300000               # Quà sinh nhật mặc định
STANDARD_WORKING_DAYS = 25           # Ngày công chuẩn nếu chưa có trong hợp đồng

# Bảng thuế lũy tiến (monthly)
PIT_BRACKETS = [
    (0, 5000000, 0.05),
    (5000000, 10000000, 0.10),
    (10000000, 18000000, 0.15),
    (18000000, 32000000, 0.20),
    (32000000, 52000000, 0.25),
    (52000000, 80000000, 0.30),
    (80000000, float('inf'), 0.35),
]

# =================== MODEL PAYROLL ===================
class EmployeePayroll(models.Model):
    _name = "employee.payroll"
    _description = "Bảng lương nhân sự hàng tháng (kết hợp UTH)"
    _rec_name = "display_name"
    _order = "year desc, month desc, employee_id"

    # ---------------- IDENTIFICATION ----------------
    employee_id = fields.Many2one('hr.employee', string="Nhân viên", required=True)
    display_name = fields.Char(string="Payslip", compute='_compute_display_name', store=True)
    staff_code = fields.Char(string="Mã nhân viên", related="employee_id.employee_code", store=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", related="employee_id.department_id", store=True)

    month = fields.Selection([(str(i), str(i)) for i in range(1, 13)], string="Tháng", required=True)
    year = fields.Selection([(str(y), str(y)) for y in range(2020, datetime.now().year + 6)], string="Năm", required=True)

    period_from = fields.Date(string="Từ ngày", compute='_compute_period', store=True)
    period_to = fields.Date(string="Đến ngày", compute='_compute_period', store=True)

    contract_id = fields.Many2one('uth.contract', string="Hợp đồng", compute='_compute_contract', store=True)

    # ---------------- CURRENCY ----------------
    company_currency = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    # ---------------- SALARY BASE ----------------
    basic_salary = fields.Float(string="Lương cơ bản (monthly)", digits=(16,2), default=5100000)
    contract_salary = fields.Float(string="Lương khoán", digits=(16,2), default=5000000)
    standard_work_days = fields.Integer(string="Ngày công chuẩn", default=STANDARD_WORKING_DAYS)

    # ---------------- ALLOWANCES ----------------
    accommodation = fields.Monetary(string="Tiền nhà ở (kỳ)", currency_field='company_currency', default=5000000)
    petro = fields.Monetary(string="Hỗ trợ xăng xe (kỳ)", currency_field='company_currency', default=5000000)
    transportation = fields.Monetary(string="Hỗ trợ đi lại (kỳ)", currency_field='company_currency', default=5000000)
    telephone = fields.Monetary(string="Tiền điện thoại (kỳ)", currency_field='company_currency', default=9000000)
    manual_allowance = fields.Monetary(string="Phụ cấp nhập tay (kỳ)", currency_field='company_currency', default=0.0)
    total_allowance = fields.Monetary(string="Tổng phụ cấp (kỳ)", currency_field='company_currency', compute='_compute_total_allowance', store=True)

    # ---------------- ATTENDANCE ----------------
    working_days = fields.Float(string="Ngày làm việc thực tế", compute='_compute_attendance', store=True)
    paid_leave_days = fields.Float(string="Ngày nghỉ hưởng lương", default=0.0)
    attendance_percent = fields.Float(string="% Chuyên cần", compute='_compute_attendance_percent', store=True)
    attendance_allowance_fixed = fields.Monetary(string="Tiền chuyên cần (fixed)", currency_field='company_currency', default=1000000)
    performance_allowance_fixed = fields.Monetary(string="Tiền hiệu suất (fixed)", currency_field='company_currency', default=2000000)
    performance_percent = fields.Float(string="% Hiệu suất", default=100.0)

    # ---------------- OVERTIME (chỉ OT approved) ----------------
    overtime_hours_15 = fields.Float(string="OT 1.5x (giờ)", compute='_compute_attendance', store=True)
    overtime_hours_20 = fields.Float(string="OT 2.0x (giờ)", compute='_compute_attendance', store=True)
    overtime_hours_21 = fields.Float(string="OT 2.1x (giờ)", compute='_compute_attendance', store=True)
    overtime_hours_27 = fields.Float(string="OT 2.7x (giờ)", compute='_compute_attendance', store=True)
    overtime_hours_30 = fields.Float(string="OT 3.0x (giờ)", compute='_compute_attendance', store=True)
    overtime_hours_39 = fields.Float(string="OT 3.9x (giờ)", compute='_compute_attendance', store=True)
    overtime_hours_total = fields.Float(string="Tổng giờ OT", compute='_compute_ot_hours_from_breakdown', store=True)
    overtime_amount_taxable = fields.Monetary(string="Tiền OT tính thuế", currency_field='company_currency', default=0.0)
    overtime_amount_nontax = fields.Monetary(string="Tiền OT không tính thuế", currency_field='company_currency', default=0.0)
    overtime_amount = fields.Monetary(string="Tổng tiền OT", currency_field='company_currency', compute='_compute_total_overtime', store=True)

    # ---------------- GROSS INCOME ----------------
    basic_salary_in_period = fields.Monetary(string="Lương cơ bản trong kỳ", currency_field='company_currency', compute='_compute_income', store=True)
    allowance_in_period = fields.Monetary(string="Tổng PC trong kỳ (HĐ pro-rata)", currency_field='company_currency', compute='_compute_income', store=True)
    attendance_allowance = fields.Monetary(string="Tiền chuyên cần trong kỳ", currency_field='company_currency', compute='_compute_income', store=True)
    performance_allowance = fields.Monetary(string="Tiền hiệu suất trong kỳ", currency_field='company_currency', compute='_compute_income', store=True)
    birthday_gift = fields.Monetary(string="Quà sinh nhật", currency_field='company_currency', compute='_compute_birthday_gift', store=True)
    other_income_manual = fields.Monetary(string="Thu nhập khác (manual)", currency_field='company_currency', default=0.0)
    other_income_total = fields.Monetary(string="Thu nhập khác (tổng)", currency_field='company_currency', compute='_compute_other_income_total', store=True)
    total_income = fields.Monetary(string="Tổng thu nhập (Gross)", currency_field='company_currency', compute="_compute_income", store=True)

    # ---------------- SOCIAL INSURANCE ----------------
    salary_for_si = fields.Monetary(string="Lương tính BHXH", currency_field='company_currency', compute='_compute_si', store=True)
    employee_si = fields.Monetary(string="NLĐ đóng BHXH", currency_field='company_currency', compute='_compute_si', store=True)
    company_si = fields.Monetary(string="DN đóng BHXH", currency_field='company_currency', compute='_compute_si', store=True)

    # ---------------- TAX ----------------
    tax_type = fields.Selection([('THUEMUOI','Thuế 10%'),('THUELUYTIEN','Thuế lũy tiến')], string="Loại thuế", default='THUELUYTIEN')
    personal_deduction = fields.Monetary(string="Giảm trừ bản thân", currency_field='company_currency', default=PERSONAL_DEDUCTION)
    num_dependents = fields.Integer(string="Số lượng NPT", default=0)
    dependent_deduction = fields.Monetary(string="Giảm trừ người phụ thuộc", currency_field='company_currency', compute='_compute_dependent', store=True)
    taxable_income = fields.Monetary(string="Thu nhập chịu thuế", currency_field='company_currency', compute='_compute_tax', store=True)
    net_taxable_income = fields.Monetary(string="Thu nhập tính thuế", currency_field='company_currency', compute='_compute_tax', store=True)
    pit_amount = fields.Monetary(string="Thuế TNCN (PIT)", currency_field='company_currency', compute='_compute_tax', store=True)

    # ---------------- ADJUSTMENTS ----------------
    advance_salary = fields.Monetary(string="Tạm ứng lương", currency_field='company_currency', default=0.0)
    collect_arrears = fields.Monetary(string="Truy thu", currency_field='company_currency', default=0.0)
    union_fee = fields.Monetary(string="Đoàn phí 1%", currency_field='company_currency', default=0.0)  # không trừ

    # ---------------- NET PAY ----------------
    net_pay = fields.Monetary(string="Thực nhận (Net)", currency_field='company_currency', compute='_compute_net_pay', store=True)

    # ---------------- METADATA ----------------
    tax_code = fields.Char(string="Mã Thuế TNCN")
    note = fields.Text(string="Ghi chú")
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed'), ('paid', 'Paid')], default='draft', string="Trạng thái")

    _sql_constraints = [
        ('unique_employee_month', 'unique(employee_id, month, year)', 'Payslip cho nhân viên này đã tồn tại trong tháng/năm này!')
    ]

    # =================== COMPUTE METHODS ===================
    @api.depends('employee_id', 'month', 'year')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.employee_id.name} - {rec.month}/{rec.year}" if rec.employee_id else "Payslip"

    @api.depends('month', 'year')
    def _compute_period(self):
        for rec in self:
            if rec.month and rec.year:
                y, m = int(rec.year), int(rec.month)
                rec.period_from = date(y, m, 1)
                rec.period_to = date(y, m, calendar.monthrange(y, m)[1])
            else:
                rec.period_from = rec.period_to = False

    @api.depends('employee_id')
    def _compute_contract(self):
        today = date.today()
        for rec in self:
            rec.contract_id = self.env['uth.contract'].sudo().search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'running'),
                '|', ('end_date', '=', False), ('end_date', '>=', today)
            ], order='start_date desc', limit=1)

    @api.depends('accommodation','petro','transportation','telephone','manual_allowance')
    def _compute_total_allowance(self):
        for rec in self:
            rec.total_allowance = sum([
                rec.accommodation or 0.0,
                rec.petro or 0.0,
                rec.transportation or 0.0,
                rec.telephone or 0.0,
                rec.manual_allowance or 0.0
            ])

    @api.depends('employee_id','period_from','period_to')
    def _compute_attendance(self):
        Attendance = self.env['employee.attendance.custom'].sudo()
        for rec in self:
            rec.working_days = 0.0
            rec.paid_leave_days = 0.0
            if rec.employee_id and rec.period_from and rec.period_to:
                atts = Attendance.search([
                    ('employee_id','=',rec.employee_id.id),
                    ('date','>=',rec.period_from),
                    ('date','<=',rec.period_to),
                    ('approval_status', '=', 'accepted')
                ])
                if atts:
                    # Số ngày làm việc = count ngày có work_hours > 0
                    rec.working_days = sum(1 for att in atts if att.work_hours > 0)
                    # Ngày nghỉ hưởng lương
                    rec.paid_leave_days = sum(att.leave_days or 0.0 for att in atts)
            
    @api.depends('working_days','standard_work_days')
    def _compute_attendance_percent(self):
        for rec in self:
            std = rec.standard_work_days or STANDARD_WORKING_DAYS
            rec.attendance_percent = round((rec.working_days or 0.0)/std*100,2) if std else 0.0

    @api.depends('overtime_hours_15','overtime_hours_20','overtime_hours_21','overtime_hours_27','overtime_hours_30','overtime_hours_39')
    def _compute_ot_hours_from_breakdown(self):
        for rec in self:
            rec.overtime_hours_total = sum([
                rec.overtime_hours_15 or 0.0,
                rec.overtime_hours_20 or 0.0,
                rec.overtime_hours_21 or 0.0,
                rec.overtime_hours_27 or 0.0,
                rec.overtime_hours_30 or 0.0,
                rec.overtime_hours_39 or 0.0
            ])

    @api.depends('overtime_amount_taxable','overtime_amount_nontax')
    def _compute_total_overtime(self):
        for rec in self:
            rec.overtime_amount = (rec.overtime_amount_taxable or 0.0) + (rec.overtime_amount_nontax or 0.0)

    @api.depends('basic_salary','total_allowance','working_days','standard_work_days',
             'attendance_allowance_fixed','performance_allowance_fixed',
             'birthday_gift','other_income_manual','overtime_amount')
    def _compute_income(self):
        for rec in self:
            if rec.working_days > 0:
                std_days = rec.standard_work_days or STANDARD_WORKING_DAYS
                worked_days = rec.working_days
                rec.basic_salary_in_period = round((rec.basic_salary/std_days)*worked_days,0) if std_days else 0.0
                rec.allowance_in_period = round((rec.total_allowance/std_days)*worked_days,0) if std_days else 0.0
                rec.attendance_allowance = round((rec.attendance_allowance_fixed/std_days)*worked_days,0) if std_days else 0.0
                rec.performance_allowance = round((rec.performance_allowance_fixed/std_days)*worked_days,0) if std_days else 0.0
            else:
                rec.basic_salary_in_period = 0.0
                rec.allowance_in_period = 0.0
                rec.attendance_allowance = 0.0
                rec.performance_allowance = 0.0

            rec.total_income = sum([
                rec.basic_salary_in_period or 0.0,
                rec.allowance_in_period or 0.0,
                rec.attendance_allowance or 0.0,
                rec.performance_allowance or 0.0,
                rec.birthday_gift or 0.0,
                rec.other_income_manual or 0.0,
                rec.overtime_amount or 0.0
            ])


    @api.depends('employee_id.dob','period_from','period_to')
    def _compute_birthday_gift(self):
        for rec in self:
            rec.birthday_gift = 0.0
            if rec.employee_id and rec.employee_id.dob and rec.period_from and rec.period_to:
                dob = rec.employee_id.dob
                try:
                    dob_this_year = date(rec.period_from.year,dob.month,dob.day)
                except ValueError:
                    dob_this_year = date(rec.period_from.year,2,28)
                if rec.period_from <= dob_this_year <= rec.period_to:
                    rec.birthday_gift = BIRTHDAY_GIFT

    @api.depends('other_income_manual')
    def _compute_other_income_total(self):
        for rec in self:
            rec.other_income_total = rec.other_income_manual or 0.0

    @api.depends('basic_salary')
    def _compute_si(self):
        for rec in self:
            rec.salary_for_si = rec.basic_salary or 0.0
            rec.employee_si = float_round(rec.salary_for_si * EMPLOYEE_SI_RATE,0)
            rec.company_si = float_round(rec.salary_for_si * COMPANY_SI_RATE,0)

    @api.depends('num_dependents')
    def _compute_dependent(self):
        for rec in self:
            rec.dependent_deduction = (rec.num_dependents or 0) * DEPENDENT_DEDUCTION

    @api.depends('total_income','employee_si','personal_deduction','num_dependents')
    def _compute_tax(self):
        for rec in self:
            dependent_deduction = (rec.num_dependents or 0) * DEPENDENT_DEDUCTION
            rec.net_taxable_income = rec.total_income - (rec.employee_si or 0.0) - rec.personal_deduction - dependent_deduction
            rec.taxable_income = max(rec.net_taxable_income,0.0)
            pit = 0.0
            taxable = rec.taxable_income
            if taxable>0:
                for lower,upper,rate in PIT_BRACKETS:
                    overlap = max(0.0,min(taxable,upper)-lower)
                    if overlap>0:
                        pit += overlap*rate
            rec.pit_amount = float_round(pit,0) if rec.net_taxable_income>0 else 0.0

    @api.depends('total_income','employee_si','pit_amount','advance_salary','collect_arrears')
    def _compute_net_pay(self):
        for rec in self:
            rec.net_pay = (rec.total_income or 0.0) - (rec.employee_si or 0.0) - (rec.pit_amount or 0.0) - (rec.advance_salary or 0.0) + (rec.collect_arrears or 0.0)

    # =================== ACTIONS ===================
    def action_confirm(self):
        for rec in self:
            rec.state='confirmed'

    def action_set_paid(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_("Payslip must be confirmed before marking paid."))
            rec.state='paid'

# =================== WIZARD ===================
class PayrollGenerateWizard(models.TransientModel):
    _name="payroll.generate.wizard"
    _description="Wizard sinh bảng lương hàng loạt"

    month = fields.Selection([(str(i),str(i)) for i in range(1,13)], string="Tháng", required=True)
    year = fields.Selection([(str(y),str(y)) for y in range(2020,datetime.now().year+6)], string="Năm", required=True)
    auto_confirm = fields.Boolean(string="Tự động confirm payslip", default=False)
    include_without_contract = fields.Boolean(string="Bao gồm nhân viên không có hợp đồng running", default=False)

    def action_generate(self):
        if not self.month or not self.year:
            raise UserError(_("Bạn phải chọn tháng và năm để tạo bảng lương."))
        employees = self.env['hr.employee'].sudo().search([])
        for emp in employees:
            today = date.today()
            contract = self.env['uth.contract'].sudo().search([
                ('employee_id','=',emp.id),
                ('state','=','running'),
                '|',('end_date','=',False),('end_date','>=',today)
            ], order='start_date desc', limit=1)
            if not contract and not self.include_without_contract:
                continue
            old = self.env['employee.payroll'].sudo().search([
                ('employee_id','=',emp.id),
                ('month','=',self.month),
                ('year','=',self.year)
            ])
            if old:
                old.sudo().unlink()
            vals={
                'employee_id': emp.id,
                'month': self.month,
                'year': self.year,
            }
            if contract:
                vals.update({
                    'contract_id': contract.id,
                    'basic_salary': float(getattr(contract,'basic_salary',0.0) or 0.0),
                    'contract_salary': float(getattr(contract,'contract_salary',0.0) or 0.0),
                })
            payslip = self.env['employee.payroll'].sudo().create(vals)
            # Compute tất cả
            payslip._compute_period()
            payslip._compute_contract()
            payslip._compute_total_allowance()
            payslip._compute_attendance()
            payslip._compute_ot_hours_from_breakdown()
            payslip._compute_income()
            payslip._compute_si()
            payslip._compute_dependent()
            payslip._compute_tax()
            payslip._compute_birthday_gift()
            payslip._compute_net_pay()
            if self.auto_confirm:
                payslip.sudo().write({'state':'confirmed'})
        _logger.info("PayrollGenerateWizard generated payslips for %s/%s",self.month,self.year)
        return {'type':'ir.actions.client','tag':'reload'}
