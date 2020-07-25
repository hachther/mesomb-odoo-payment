import json
import logging
import pprint

from werkzeug import urls

from odoo import api, fields, models, _
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.addons.payment_mesomb.controllers.main import MeSombController

_logger = logging.getLogger(__name__)

# The following currencies are integer only, see https://mesomb.com/docs/currencies#zero-decimal
INT_CURRENCIES = [u'XAF']


class AcquirerMeSomb(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('mesomb', 'MeSomb')])
    mesomb_application_key = fields.Char('Application Key', help="Provide by MeSomb", required_if_provider='mesomb',
                                         groups='base.group_user')
    mesomb_include_fees = fields.Boolean('Include Fees',
                                         help="Check if should by add to the amount deducted to the customer",
                                         required_if_provider='mesomb',
                                         groups='base.group_user')

    def mesomb_form_generate_values(self, values):
        base_url = self.get_base_url()

        mesomb_tx_values = dict(values)
        mesomb_tx_values.update({
            'app': self.mesomb_application_key,
            'fees': self.mesomb_include_fees,
            'item_name': '%s: %s' % (self.company_id.name, values['reference']),
            'item_number': values['reference'],
            'amount': values['amount'],
            'currency_code': values['currency'] and values['currency'].name or '',
            'address1': values.get('partner_address'),
            'city': values.get('partner_city'),
            'country': values.get('partner_country') and values.get('partner_country').code or '',
            'state': values.get('partner_state') and (
                        values.get('partner_state').code or values.get('partner_state').name) or '',
            'email': values.get('partner_email'),
            'zip_code': values.get('partner_zip'),
            'first_name': values.get('partner_first_name'),
            'last_name': values.get('partner_last_name'),
            'mesomb_return': urls.url_join(base_url, MeSombController._pay_url),
            'notify_url': urls.url_join(base_url, MeSombController._notify_url),
            'cancel_return': urls.url_join(base_url, MeSombController._cancel_url),
            'custom': json.dumps({'return_url': '%s' % mesomb_tx_values.pop('return_url')}) if mesomb_tx_values.get(
                'return_url') else False,
        })
        return mesomb_tx_values

    def mesomb_get_form_action_url(self):
        self.ensure_one()
        environment = 'prod' if self.state == 'enabled' else 'test'
        return self._get_mesomb_urls(environment)['mesomb_form_url']

    def mesomb_get_rest_action_url(self):
        self.ensure_one()
        environment = 'prod' if self.state == 'enabled' else 'test'
        return self._get_mesomb_urls(environment)['mesomb_rest_url']


    @api.model
    def _get_mesomb_urls(self, environment):
        return {
            'mesomb_form_url': 'http://127.0.0.1:8000/en/external/payment/',
            'mesomb_rest_url': 'https://mesomb.hachther.com/api/v1.0/payment/online/',
        }


class TrxMeSomb(models.Model):
    _inherit = 'payment.transaction'

    mesomb_payer_phone = fields.Char('Phone Number')
    mesomb_payer_operator = fields.Selection([('ORANGE', 'Orange Money'), ('MTN', 'Mobile Money')], 'Mobile Operator')

    @api.model
    def _mesomb_form_get_tx_from_data(self, data):
        reference = data.get('reference')
        if not reference:
            error_msg = _('MeSomb: received data with missing reference (%s) ') % reference
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        txs = self.env['payment.transaction'].search([('reference', '=', reference)])
        if not txs or len(txs) > 1:
            error_msg = 'MeSomb: received data for reference %s' % reference
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

    def _mesomb_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        _logger.info('Received a notification from Paypal with IPN version %s', data.get('notify_version'))

    def _mesomb_form_validate(self, data):
        self.ensure_one()
        if self.state not in ("draft", "pending"):
            _logger.info('MeSomb: trying to validate an already validated tx (ref %s)', self.reference)
            return True

        status = data.get('status')
        tx_id = data.get('txn_id')
        vals = {
            "date": fields.datetime.now(),
            "acquirer_reference": tx_id
        }
        if status == 'SUCCESS':
            self.write(vals)
            self._set_transaction_done()
            self.execute_callback()
            return True
        else:
            error = data.get("message")
            self._set_transaction_error(error)
            return False
