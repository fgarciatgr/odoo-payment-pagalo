# -*- coding: utf-8 -*-

import logging
import hmac
import hashlib
import json
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PagaloPaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_processing_values(self, processing_values):
        """
        Sobrescribe el método de Odoo para añadir lógica específica
        antes de que se procese cualquier dato de feedback (retorno o webhook).
        """
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'pagalo':
            return res
        
        # El feedback real viene del webhook, no del retorno del cliente.
        # Aquí validamos la firma si es un webhook.
        self._verify_pagalo_signature(processing_values)
        
        return res

    def _verify_pagalo_signature(self, data):
        """
        Verifica la firma del webhook para asegurar que la petición es de Pagalo.
        """
        # La firma solo viene en el webhook, no en los datos de retorno del cliente.
        received_signature = data.get('pgl_signature')
        if not received_signature:
            # Si no hay firma, no es un webhook validable, así que no hacemos nada.
            # Esto es normal cuando el cliente es redirigido de vuelta al sitio.
            _logger.info("No se encontró firma de Pagalo en los datos. Asumiendo retorno de cliente, no webhook.")
            return

        _logger.info("Validando firma del webhook de Pagalo.")
        secret_key = self.acquirer_id.pagalo_secret_key
        if not secret_key:
            _logger.error("Falta la 'Secret Key' de Pagalo para la transacción %s. No se puede validar el webhook.", self.reference)
            raise ValidationError("Pagalo: Falta la Secret Key para validar la notificación.")

        # Recreamos el payload original que Pagalo usó para generar la firma.
        # Pagalo firma el cuerpo del POST como una cadena de texto.
        # El controlador ya puso el cuerpo del JSON en 'data'.
        # Debemos quitar nuestra clave 'pgl_signature' y re-serializar el resto.
        webhook_payload = {k: v for k, v in data.items() if k != 'pgl_signature'}
        
        # Pagalo requiere que el JSON no tenga espacios entre claves y valores.
        payload_string = json.dumps(webhook_payload, separators=(',', ':')).encode('utf-8')
        secret_bytes = secret_key.encode('utf-8')

        # Calculamos nuestra propia firma usando HMAC-SHA256
        expected_signature = hmac.new(secret_bytes, payload_string, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_signature, received_signature):
            _logger.warning("Fallo en la validación de firma para la transacción %s. Firma esperada: %s, firma recibida: %s",
                            self.reference, expected_signature, received_signature)
            raise ValidationError("Pagalo: Firma del webhook inválida.")

        _logger.info("Firma del webhook de Pagalo validada exitosamente para la transacción %s.", self.reference)

    def _get_tx_from_feedback_data(self, provider_code, data):
        """
        Encuentra la transacción de Odoo correspondiente a los datos recibidos.
        """
        if provider_code != 'pagalo':
            return super()._get_tx_from_feedback_data(provider_code, data)
        
        # Pagalo nos devuelve nuestro 'transactionId' en el webhook, que es la referencia de Odoo.
        reference = data.get('transactionId')
        if not reference:
            raise ValidationError("Pagalo: La notificación no contenía una referencia de transacción.")
            
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'pagalo')])
        if not tx:
            raise ValidationError(f"Pagalo: No se encontró ninguna transacción para la referencia {reference}.")
        return tx

    def _process_feedback_data(self, data):
        """
        Procesa el feedback (del webhook) después de que ha sido validado.
        """
        super()._process_feedback_data(data)
        if self.provider_code != 'pagalo':
            return
            
        # El estado de la transacción viene en el campo 'status' del webhook.
        status = data.get('status')
        
        if status == 'AUTHORIZED':
            _logger.info("Transacción %s autorizada por Pagalo.", self.reference)
            self._set_done()
        elif status in ['DECLINED', 'ERROR']:
            error_message = data.get('statusMessage', 'El pago fue declinado o falló.')
            _logger.warning("Transacción %s fallida en Pagalo. Estado: %s, Mensaje: %s", self.reference, status, error_message)
            self._set_canceled(state_message=error_message)
        else:
            # Para cualquier otro estado (ej. PENDING), simplemente registramos y dejamos la transacción en borrador.
            _logger.info("Transacción %s con estado pendiente en Pagalo: %s", self.reference, status)
            self._set_pending()

