{
    'name': 'Employee Leave Custom',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Quản lý nghỉ phép, cấp phát ngày lễ và dashboard lịch nghỉ',
    'description': """
        - Tạo đơn nghỉ phép / giải trình
        - Workflow duyệt phép: Trưởng đơn vị → P.TC-HC/Hiệu trưởng → Hoàn thành
        - Kanban/List/Form view
        - Calendar view / Dashboard lịch nghỉ
        - Tự động cấp phát ngày phép đầu năm
        - Cấp phát ngày lễ Việt Nam
        - Phân quyền xem theo nhân viên
    """,
    'author': 'Your Name',
    'depends': ['base', 'hr', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu_views.xml',
        'views/leave_views.xml',
        'views/leave_dashboard.xml',
        'views/employee_leave_type.xml',
    ],
    'installable': True,
    'application': True,
}
