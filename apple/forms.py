# -*- coding: utf-8 -*-
from django import forms
from . import app_store_verify_receipt
import logging

log = logging.getLogger()


class AppleStoreVerifyReceipt(forms.Form):
    receipt_data = forms.Field()
    response_data = None

    def clean(self):
        data = app_store_verify_receipt(self.cleaned_data['receipt_data'])
        if not data or 'receipt' not in data:
            log.error('app store verify receipt returned:\n%s\n for:\n%s' % (data, self.cleaned_data['receipt_data']))
            raise forms.ValidationError('apple verify receipt does not return correct data')
        self.response_data = data
        return self.cleaned_data


class GameCenterAuthenticationForm(forms.Form):
    """Форма для авторизации пользователя из Apple GameCenter"""
    playerId = forms.CharField()
    bundleId = forms.CharField()
    publicKeyUrl = forms.CharField()
    signature = forms.CharField()
    salt = forms.CharField()
    timestamp = forms.CharField()

    def clean(self):
        from Crypto.PublicKey import RSA
        from Crypto.Signature import PKCS1_v1_5
        from Crypto.Hash import SHA256
        from base64 import b64decode
        from Crypto.Util.asn1 import DerSequence
        # from binascii import a2b_base64
        import struct
        import urllib2
        import urlparse

        player_id = self.cleaned_data['playerId']
        bundle_id = self.cleaned_data['bundleId']
        public_key_url = self.cleaned_data['publicKeyUrl']
        signature = self.cleaned_data['signature']
        salt = self.cleaned_data['salt']
        timestamp = self.cleaned_data['timestamp']

        apple_cert = urllib2.urlopen(public_key_url).read()
        uri = urlparse.urlparse(public_key_url)
        domain_name = "apple.com"
        domain_location = len(uri.netloc) - len(domain_name)
        actual_location = uri.netloc.find(domain_name)
        if uri.scheme != "https" or domain_name not in uri.netloc or domain_location != actual_location:
            raise forms.ValidationError('Public Key Url is invalid', code='publicKeyUrl')

        cert = DerSequence()
        cert.decode(apple_cert)
        tbs_certificate = DerSequence()
        tbs_certificate.decode(cert[0])
        subject_public_key_info = tbs_certificate[6]

        rsa_key = RSA.importKey(subject_public_key_info)
        verifier = PKCS1_v1_5.new(rsa_key)

        payload = player_id.encode('UTF-8')
        payload = payload + bundle_id.encode('UTF-8')
        payload = payload + struct.pack('>Q', int(timestamp))
        payload = payload + b64decode(salt)
        digest = SHA256.new(payload)

        if not verifier.verify(digest, b64decode(signature)):
            raise forms.ValidationError('The signature is not authentic', code='signature')
        return self.cleaned_data

    def get_player_id(self):
        return self.cleaned_data['playerId']
