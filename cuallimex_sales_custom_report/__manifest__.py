{
    "name": "Cuallimex Sales Custom Report",
    "version": "13.2020.10.30-01",
    "description": """
        Customized sales report for Cuallimex
    """,
    "category": "",
    'summary':"Custom Quote and Sales order",
    "depends": [
        "account",
        "sale_stock",
        "sale_management"
    ],
    "data": [
        'security/security.xml',
        'views/sale_order_view.xml',
        'report/sale_order_details_report.xml',
        'report/report_view.xml',
        # 'views/report_template_view.xml',
    ],
    'qweb': [],
    'css': [],
    'js': [],
    'images': [],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
