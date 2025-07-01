# -*- coding: utf-8 -*-

import logging
import requests
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from werkzeug.urls import url_join

_logger = logging.getLogger(__name__)

class PagaloPaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(
        selection_add=[('pagalo', 'Pagalo V2')],
        ondelete={'pagalo': 'set default'}
    )
    pagalo_api_key = fields.Char(
        string='Pagalo API Key',
        help='La API Key proporcionada por Pagalo.',
        required_if_provider='pagalo',
        groups='base.group_system'
    )
    pagalo_secret_key = fields.Char(
        string='Pagalo Secret Key',
        help='La Secret Key utilizada para validar los webhooks.',
        required_if_provider='pagalo',
        password=True,
        groups='base.group_system'
    )

    # --- Helper Methods ---

    def _get_pagalo_api_url(self):
        """Devuelve la URL base de la API de Pagalo según el entorno."""
        self.ensure_one()
        if self.state == 'test':
            # Asumimos una URL de prueba. ESTA URL DEBE SER VERIFICADA CON PAGALO.
            _logger.info("Usando entorno de PRUEBA de Pagalo.")
            return 'https://test-api.pagalo.co' # URL de prueba (hipotética)
        else: # 'enabled'
            _logger.info("Usando entorno de PRODUCCIÓN de Pagalo.")
            return 'https://api.pagalo.co' # URL de producción

    def _get_pagalo_checkout_url(self):
        """Devuelve la URL de la pasarela de pago según el entorno."""
        self.ensure_one()
        if self.state == 'test':
            # Asumimos una URL de prueba. ESTA URL DEBE SER VERIFICADA CON PAGALO.
            return 'https://test.pagalo.co' # URL de prueba (hipotética)
        else: # 'enabled'
            return 'https://www.pagalo.co' # URL de producción

    # --- Core Integration Method ---

    def _get_redirect_form(self, tx_sudo, landing_url, **kwargs):
        """
        Prepara los datos, llama a la API de Pagalo para crear una transacción y
        genera el formulario de redirección.
        """
        self.ensure_one()
        if self.provider != 'pagalo':
            return super()._get_redirect_form(tx_sudo, landing_url, **kwargs)

        base_url = self.get_base_url()
        return_url = url_join(base_url, '/payment/pagalo/return')
        
        payload = {
            'amount': tx_sudo.amount,
            'description': tx_sudo.reference,
            'email': tx_sudo.partner_email,
            'currency': tx_sudo.currency_id.name,
            'source': 'odoo_v18_integration',
            'successUrl': return_url,
            'failUrl': return_url,
            'transactionId': tx_sudo.reference
        }

        headers = {
            'Content-Type': 'application/json',
            'PGL-API-KEY': self.pagalo_api_key
        }

        api_url = url_join(self._get_pagalo_api_url(), '/v2/transaction/create')
        try:
            _logger.info("Enviando petición de creación de transacción a Pagalo para %s a la URL %s", tx_sudo.reference, api_url)
            response = requests.post(api_url, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            response_data = response.json()
            
            transaction_token = response_data.get('transactionToken')
            if not transaction_token:
                _logger.error("Respuesta de Pagalo sin transactionToken: %s", response_data)
                raise ValidationError("Pagalo no devolvió un token de transacción válido.")

        except requests.exceptions.RequestException as e:
            _logger.error("Error al contactar la API de Pagalo: %s", e)
            raise ValidationError("No se pudo establecer conexión con la pasarela de pagos. Por favor, intente de nuevo más tarde.")
        except Exception as e:
            _logger.error("Error inesperado procesando pago con Pagalo: %s", e)
            raise

        redirect_url = url_join(self._get_pagalo_checkout_url(), f"/debit/{transaction_token}")

        return {
            'url': redirect_url,
            'method': 'get',
            'params': {},
        }
