{
    'name': 'UTH Overview',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Tổng quan Trường ĐH GTVT TP.HCM',
    'description': '''
        Quản lý tổng quan Trường ĐH GTVT TP.HCM:
        - Cơ sở
        - Cấp phân quyền
        - Lĩnh vực: Giáo dục
    ''',
    'author': 'DUY',
    'depends': ['base','mail'],
    'data': [
        'security/hrm_groups.xml',
        'security/ir.model.access.csv',
        'views/uth_views.xml',
        'data/initial_data.xml',
    ],
    'installable': True,
    'application': True,
}
