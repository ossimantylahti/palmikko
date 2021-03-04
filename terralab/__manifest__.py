# -*- coding: utf-8 -*-
{
    'name': "TerraLab",

    'summary': """
        TerraLab System""",

    'description': """
        TerraLab extends Odoo by adding laboratory management functions.
    """,

    'author': "TerraLab Oy",
    'website': "https://www.terralab.fi",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Specific Industry Applications',
    'version': '0.10',

    # any module necessary for this one to work correctly
    'depends': ['base', 'product', 'sale', 'google_spreadsheet'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/sites.xml',
        'reports/terralab_test_report.xml',
        'views/sample_type_views.xml',
        'views/test_variable_type_views.xml',
        'views/spreadsheet_views.xml',
        'views/order_views.xml',
        'views/sample_views.xml',
        'views/test_views.xml',
        'views/test_variable_views.xml',
        'views/report_views.xml',
        'views/product_form.xml',
        'views/order_form.xml',
        'views/menu_actions.xml',
        'views/menu_items.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,

    # PIP requirements - install with pip3 install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib oauth2client
    'external_dependencies': {
        'python': ['google-api-python-client', 'google-auth', 'google-auth-httplib2', 'google-auth-oauthlib', 'oauth2client'],
    },
}
