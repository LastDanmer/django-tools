""" django settings:
APP_STORE_VERIFY_RECEIPT_URL - bool
APP_STORE_CERT_FILE_PATH - string
APP_STORE_KEY_FILE_PATH - string
APP_STORE_PUSH_SANDBOX - bool (equals DEBUG)
"""
import logging

_logger = logging.getLogger(__name__)


def app_store_verify_receipt(receipt_data):
    from django.conf import settings
    import requests
    url = 'https://sandbox.itunes.apple.com/verifyReceipt'
    if getattr(settings, 'APP_STORE_VERIFY_RECEIPT_URL', False):
        url = 'https://buy.itunes.apple.com/verifyReceipt'
    resp = requests.post(url, json={'receipt-data': receipt_data})
    if resp.ok:
        return resp.json()


def push_notification(device_token, **payloads):
    # requires: apns (tested: 2.0.1)
    def response_listener(error_response):
        _logger.error('push_notification response error: %s' % error_response)

    from apns import APNs, Payload
    from django.conf import settings
    if getattr(settings, 'APP_STORE_PUSH_TO_NULL', False):
        return None
    cert_file = getattr(settings, 'APP_STORE_CERT_FILE_PATH')
    key_file = getattr(settings, 'APP_STORE_KEY_FILE_PATH')
    use_sandbox = getattr(settings, 'APP_STORE_PUSH_SANDBOX', True)
    payload = Payload(**payloads)
    apns = APNs(use_sandbox=use_sandbox, cert_file=cert_file, key_file=key_file, enhanced=True)
    apns.gateway_server.register_response_listener(response_listener)
    apns.gateway_server.send_notification(device_token, payload)
    _logger.info('sent notification to %s' % device_token)
    for (token, failed_time) in apns.feedback_server.items():
        _logger.error("failed: " + str(token) + "\tmsg: " + str(failed_time))
    return apns
