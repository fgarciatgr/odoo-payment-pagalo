# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Payment Acquirer: Pagalo V2',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Payment Acquirers',
    'sequence': 350,
    'summary': 'Integración de la pasarela de pagos Pagalo V2 con Odoo.',
    'description': """
Este módulo integra Pagalo V2 como un método de pago en Odoo.
Permite a los clientes pagar sus pedidos del sitio web a través de la plataforma de Pagalo.
    """,
    'author': 'Comercializadora Textil GR, S.A.',
    'website': 'https://www.textilesgr.com', # Opcional
    'depends': [
        'payment',
        'website_sale',
    ],
    'data': [
        'views/payment_acquirer_views.xml',
        'views/payment_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'OPL-1',
    'price': '100.00',
    'currency': 'usd',
}
