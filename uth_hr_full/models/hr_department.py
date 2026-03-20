# ================= Phòng ban (Department) =================
from odoo import models, fields, api

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    manager_id = fields.Many2one('hr.employee', string='Quản lý')
    deputy_ids = fields.Many2many('hr.employee', string='Cấp phó')
    employee_ids = fields.One2many('hr.employee', 'department_id', string='Nhân viên')
    employee_count = fields.Integer('Số nhân viên', compute='_compute_employee_count')

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for dept in self:
            dept.employee_count = len(dept.employee_ids)

    def action_view_employees(self):
        """Mở danh sách nhân viên của phòng ban"""
        self.ensure_one()
        return {
            'name': f'Nhân viên - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'kanban,form',
            'domain': [('department_id', '=', self.id)],
            'context': {'default_department_id': self.id},
        }
