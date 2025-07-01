# -*- coding: utf-8 -*-

import logging
import pprint
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PagaloController(http.Controller):
    _return_url = '/payment/pagalo/return'
    _webhook_url = '/payment/pagalo/webhook'

    @http.route(_return_url, type='http', auth='public', methods=['GET'], csrf=False)
    def pagalo_return_from_checkout(self, **data):
        """
        Ruta a la que Pagalo redirige al cliente después del pago.

        Los datos recibidos aquí no se utilizan para confirmar la transacción,
        ya que podrían ser manipulados por el cliente. La confirmación real
        proviene del webhook.
        """
        _logger.info("Cliente regresó desde Pagalo. Datos: %s", pprint.pformat(data))
        
        # Pasamos los datos recibidos al método genérico de Odoo, que encontrará
        # la transacción correspondiente y la procesará.
        # El estado de la transacción quedará como 'pendiente' hasta que llegue el webhook.
        request.env['payment.transaction']._handle_feedback_data('pagalo', data)
        
        # Redirigimos al cliente a la página estándar de estado del pago de Odoo.
        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='json', auth='public', methods=['POST'], csrf=False)
    def pagalo_webhook(self):
        """
        Ruta para recibir notificaciones (webhooks) desde el servidor de Pagalo.
        Esta es la única fuente fiable para confirmar el estado de una transacción.

        La ruta es 'type="json"' para que Odoo parsee automáticamente el cuerpo
        de la petición JSON entrante.
        """
        # El cuerpo de la petición JSON es accesible a través de request.jsonrequest
        data = request.jsonrequest
        _logger.info("Webhook de Pagalo recibido: %s", pprint.pformat(data))

        # El header de la firma es crucial para la seguridad.
        # Los headers se transforman a mayúsculas y se les añade HTTP_
        signature_header = request.httprequest.headers.get('PGL-SIGNATURE')

        if not data or not signature_header:
            _logger.warning("Webhook de Pagalo recibido sin datos o sin firma.")
            # Aunque no podemos procesarlo, respondemos 200 OK para que Pagalo
            # no siga intentando enviar la notificación.
            return

        try:
            # Añadimos la firma a los datos para procesarlos juntos
            data['pgl_signature'] = signature_header
            # Delegamos el procesamiento y la validación de la firma al modelo
            request.env['payment.transaction']._handle_feedback_data('pagalo', data)
        except Exception as e:
            # En caso de un error inesperado, lo registramos.
            _logger.exception("Error al procesar el webhook de Pagalo: %s", e)
            # Devolvemos un error para que Pagalo pueda intentar reenviar la notificación si está configurado para ello.
            # (El comportamiento exacto depende de la implementación de Pagalo).
            # Por ahora, simplemente no hacemos nada para evitar un ciclo infinito si el error persiste.
        
        # Siempre respondemos a Pagalo para confirmar la recepción.
        # El método es type='json', Odoo se encarga de la respuesta.
        return

