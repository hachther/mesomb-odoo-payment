# -*- coding: utf-8 -*-
import logging
import werkzeug
import pprint

import requests

from odoo import http
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class MeSombController(http.Controller):
    _notify_url = '/payment/mesomb/notify/'
    _pay_url = '/payment/mesomb/pay/'
    _cancel_url = '/payment/mesomb/cancel/'

    def mesomb_validate_data(self, **post):
        """ MeSomb Success: three steps validation to ensure data correctness

                 - step 1: return an empty HTTP 200 response -> will be done at the end
                   by returning ''
                 - step 2: POST the complete, unaltered message back to MeSomb, with same encoding
                 - step 3: MeSomb send either SUCCESS or FAIL (+ data)

                Once data is validated, process it. """
        res = False
        post['payer'] = '237' + post['payer']
        reference = post.get('reference')
        tx = None
        if reference:
            tx = request.env['payment.transaction'].sudo().search([('reference', '=', reference)])
        mesomb_url = tx.acquirer_id.mesomb_get_rest_action_url()
        app = tx.acquirer_id.mesomb_application_key
        headers = {
            'X-MeSomb-Application': app,
            'Content-Type': 'application/json'
        }
        urequest = requests.post(mesomb_url, headers=headers, json=post)
        urequest.raise_for_status()
        resp = urequest.json()
        success = resp['success']
        status = resp.get('status', 'SUCCESS' if success else 'FAIL')
        message = resp.get('message')
        txn_id = None
        if status == 'SUCCESS':
            txn_id = resp.get('transaction', {}).get('pk')

        if status == 'SUCCESS':
            _logger.info('MeSomb: validated data')
            post['status'] = status
            post['txn_id'] = txn_id
            post['message'] = message
            res = request.env['payment.transaction'].sudo().form_feedback(post, 'mesomb')
            if not res and tx:
                tx._set_transaction_error('Validation error occured. Please contact your administrator.')

        elif status == 'FAIL':
            _logger.warning('MeSomb: answered FAIL on data verification')
            if tx:
                tx._set_transaction_error('Invalid response from MeSomb. Please contact your administrator.')

        else:
            _logger.warning(
                'MeSomb: unrecognized mesomb answer, received %s instead of SUCCESS or FAIL' % (status))
            if tx:
                tx._set_transaction_error('Unrecognized error from MeSomb. Please contact your administrator.')

        return res

    @http.route('/payment/mesomb/pay/', type='http', auth='public', methods=['POST'], csrf=False)
    def mesomb_pay(self, **post):
        """ MeSomb SUCCESS. """
        _logger.info('Beginning MeSomb Success form_feedback with post data %s', pprint.pformat(post))  # debug
        try:
            self.mesomb_validate_data(**post)
        except ValidationError:
            _logger.exception('Unable to validate the MeSomb payment')
        return werkzeug.utils.redirect('/payment/process')

