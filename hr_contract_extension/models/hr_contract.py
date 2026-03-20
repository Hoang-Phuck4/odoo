# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import timedelta, date
import logging

_logger = logging.getLogger(__name__)

# ==================== LOẠI HỢP ĐỒNG ====================
class UTHContractType(models.Model):
    _name = 'uth.contract.type'
    _description = 'Loại hợp đồng nhân sự'
    _order = 'name'

    name = fields.Char(string='Tên loại hợp đồng', required=True)
    code = fields.Char(string='Mã loại', required=True)
    note = fields.Text(string='Ghi chú')

# ==================== PHỤ CẤP HỢP ĐỒNG ====================
class UTHContractAllowance(models.Model):
    _name = 'uth.contract.allowance'
    _description = 'Phụ cấp hợp đồng nhân sự'

    contract_id = fields.Many2one('uth.contract', string='Hợp đồng', required=True, ondelete='cascade')
    name = fields.Char(string='Tên phụ cấp', required=True)
    amount = fields.Float(string='Số tiền', required=True, default=0.0)

# ==================== HỢP ĐỒNG NHÂN SỰ ====================
class UTHContract(models.Model):
    _name = 'uth.contract'
    _description = 'Hợp đồng nhân sự UTH'
    _order = 'start_date desc'

    is_khoan = fields.Boolean(
    string="Hợp đồng khoán",
    compute="_compute_is_khoan",
    store=True
)

    @api.depends("contract_type_id")
    def _compute_is_khoan(self):
        for rec in self:
            rec.is_khoan = rec.contract_type_id and rec.contract_type_id.name == "Khoán"


    # -------------------- THÔNG TIN CƠ BẢN --------------------
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    name = fields.Char(string='Số hợp đồng', required=True, copy=False, readonly=True, default='New')
    contract_type_id = fields.Many2one('uth.contract.type', string='Loại hợp đồng', required=True)
    start_date = fields.Date(string='Ngày ký', required=True)
    end_date = fields.Date(string='Ngày hết hạn')

    employee_name = fields.Char(string='Tên nhân sự', compute='_compute_employee_info', store=True)
    position = fields.Char(string='Chức vụ', compute='_compute_employee_info', store=True)
    department = fields.Char(string='Đơn vị', compute='_compute_employee_info', store=True)
    notes = fields.Text(string='Ghi chú')

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Đã gửi duyệt'),
        ('running', 'Đang chạy'),
        ('rejected', 'Từ chối'),
        ('expired', 'Hết hạn')
    ], string='Trạng thái', default='draft', tracking=True)

    # -------------------- LƯƠNG & PHỤ CẤP --------------------
    basic_salary = fields.Float(string='Lương cơ bản', default=0.0)
    contract_salary = fields.Float(string='Lương khoán', default=0.0)
    display_salary = fields.Float(string='Lương hiển thị', default=0.0)

    allowance_line_ids = fields.One2many('uth.contract.allowance', 'contract_id', string='Phụ cấp chi tiết')
    total_allowance = fields.Float(string='Tổng phụ cấp', compute='_compute_total_allowance', store=True)

    # -------------------- LỊCH LÀM VIỆC --------------------
    calendar_id = fields.Many2one('resource.calendar', string='Lịch làm việc')
    attendance_ids = fields.One2many('resource.calendar.attendance', 'calendar_id', string='Working Hours')

    # ==================== TÍNH TOÁN ====================
    @api.depends('employee_id')
    def _compute_employee_info(self):
        for rec in self:
            if rec.employee_id:
                rec.employee_name = rec.employee_id.name or ''
                rec.department = rec.employee_id.department_id.name or ''
                rec.position = rec.employee_id.job_title or ''
            else:
                rec.employee_name = ''
                rec.department = ''
                rec.position = ''

    @api.depends('allowance_line_ids.amount')
    def _compute_total_allowance(self):
        for rec in self:
            rec.total_allowance = sum(line.amount for line in rec.allowance_line_ids)

    # ==================== OVERRIDE CREATE ====================
    @api.model
    def create(self, vals):
        # Sinh số hợp đồng tự động
        if vals.get('name', 'New') == 'New':
            last_contract = self.search([], order='id desc', limit=1)
            if last_contract and last_contract.name.startswith('HD'):
                last_number = int(last_contract.name.replace('HD','')) if last_contract.name else 0
                vals['name'] = 'HD%03d' % (last_number + 1)
            else:
                vals['name'] = 'HD001'

        return super().create(vals)

    # ==================== ACTIONS ====================
    def action_submit(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'submitted'

    def action_approve(self):
        for rec in self:
            if rec.state == 'submitted':
                rec.state = 'running'

    def action_reject(self):
        for rec in self:
            if rec.state == 'submitted':
                rec.state = 'rejected'

    def action_renew(self, days=365):
        for rec in self:
            if rec.state == 'expired' and rec.end_date:
                rec.end_date += timedelta(days=days)
                rec.state = 'running'

    # ==================== CRON / UPDATE ====================
    @api.model
    def cron_check_contract_expiry(self):
        today = date.today()
        contracts = self.search([('end_date', '<', today)])
        for rec in contracts:
            if rec.state not in ['draft', 'rejected', 'expired']:
                rec.state = 'expired'

    def action_update_state(self):
        today = date.today()
        contracts = self.search([('end_date', '<', today)])
        for rec in contracts:
            if rec.state not in ['draft', 'rejected', 'expired']:
                rec.state = 'expired'

# ==================== SCRIPT CONVERT DỮ LIỆU CŨ ====================
def convert_old_contract_type(env):
    """
    Convert tất cả giá trị string cũ 'vien_chuc' sang contract_type_id hợp lệ
    """
    ContractType = env['uth.contract.type']
    Contract = env['uth.contract']

    # Tạo hoặc tìm record 'Viên chức'
    ct = ContractType.search([('name','=','Viên chức')], limit=1)
    if not ct:
        ct = ContractType.create({'name':'Viên chức', 'code':'VC'})

    # Lấy tất cả contract có giá trị contract_type cũ là 'vien_chuc'
    contracts = Contract.search([('contract_type', '=', 'vien_chuc')])
    contracts.write({'contract_type_id': ct.id})
