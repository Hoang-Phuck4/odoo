{
    "name": "UT HR Payroll",
    "version": "1.0",
    "summary": "Quản lý bảng lương, phụ cấp, OT",
    "category": "Human Resources",
    "author": "UT HR",
    "website": "",
    "depends": ["base", "hr","hr_contract_extension","employee_attendance_custom","hrm_overview"],
    "data": [
        'security/ir.model.access.csv',  
        "views/payroll_views.xml",
    ],
    "installable": True,
    "application": True,
}

