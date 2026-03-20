{
    'name': 'HR Contract',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Quản lý hợp đồng và cảnh báo hết hạn',
    'description': """
        Module mở rộng cho hr_contract:
        - Thêm loại hợp đồng (Viên chức, Cơ hữu, Khoán)
        - Thêm trường thông tin cá nhân, quá trình công tác
        - Tự động tính ngày cảnh báo hết hạn hợp đồng
        - Cron job gửi thông báo trước khi hết hạn hợp đồng
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': ['base','hr','hrm_overview','resource'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/hr_contract_views.xml',
        'data/cron_data.xml',
        'data/working_hours.xml',
    ],
    'installable': True,
    'application': True,
}
