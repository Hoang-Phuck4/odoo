
{
    'name': 'UTH HR',
    'version': '1.0',
    'summary': 'Quản lý nhân sự UTH',
    'description': 'Module quản lý nhân sự đầy đủ, bao gồm nhân viên, phòng ban, loại nhân viên, học vị, trạng thái.',
    'category': 'Human Resources',
    'author': 'Your Name',
    'depends': ['base', 'hr','hrm_overview'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',  
        'data/departments.xml',
        'data/employee_types_and_degrees.xml',
        'views/hr_employee_views.xml',
        'views/hr_department_views.xml',
        'views/employee_type_views.xml',
        'views/degree_views.xml',
        'views/employee_status_views.xml',
        'views/menus.xml',
        'data/employees.xml'
    ],
    'installable': True,
    'application': True,
}
