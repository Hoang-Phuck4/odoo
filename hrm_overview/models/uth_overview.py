from odoo import models, fields

# ================= Tổng quan trường =================
class CompanyOverview(models.Model):
    _name = 'edu.company.overview'
    _description = 'Tổng quan trường đại học'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Tên trường', required=True, default='Trường Đại học Giao thông Vận tải TP.HCM')
    business_field = fields.Char('Lĩnh vực', default='Giáo dục')
    facility_ids = fields.One2many('edu.company.facility', 'company_overview_id', string='Cơ sở')
    permission_level_ids = fields.One2many('edu.permission.level', 'company_overview_id', string='Cấp phân quyền')


# ================= Cơ sở =================
class CompanyFacility(models.Model):
    _name = 'edu.company.facility'
    _description = 'Cơ sở trường đại học'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Tên cơ sở', required=True)
    address = fields.Char('Địa chỉ')
    manager_id = fields.Many2one('res.users', string='Quản lý cơ sở')
    company_overview_id = fields.Many2one('edu.company.overview', string='Tổng quan trường')


# ================= Cấp phân quyền =================
class PermissionLevel(models.Model):
    _name = 'edu.permission.level'
    _description = 'Cấp phân quyền trường đại học'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Tên cấp', required=True)
    code = fields.Selection([
        ('level_1', 'Ban lãnh đạo'),
        ('level_2', 'Trưởng phòng/Giám đốc trung tâm'),
        ('level_3', 'Phó phòng/Phó giám đốc'),
        ('level_4', 'Nhân viên/Giảng viên'),
    ], string='Mã cấp', required=True)
    description = fields.Text('Mô tả quyền hạn')
    company_overview_id = fields.Many2one('edu.company.overview', string='Tổng quan trường')
