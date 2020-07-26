# -*- coding: utf-8 -*-

{
    'name': 'MeSomb Payment Acquirer',
    'category': 'Accounting/Payment',
    'summary': 'Payment Acquirer: MeSomb Implementation for (Orange Money, Mobile Money, ...)',
    'author': 'Hachther LLC',
    'version': '1.0',
    'description': """MeSomb Payment Acquirer""",
    'depends': ['payment'],
    'data': [
        'data/payment_icon_data.xml',
        'views/payment_views.xml',
        'views/payment_mesomb_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'images': ['static/src/img/icon.png'],
    'installable': True,
    'post_init_hook': 'create_missing_journal_for_acquirers',
    'uninstall_hook': 'uninstall_hook',
}
