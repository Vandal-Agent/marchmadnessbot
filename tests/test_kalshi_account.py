import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from football_v2.kalshi_account import AccountClient, AccountError, balance_values, quantity


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.path = Path(self.directory.name) / 'key.pem'
        self.path.write_bytes(self.key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        self.path.chmod(0o600)
        self.session = Mock()
        self.client = AccountClient('test-id', self.path, session=self.session)

    def response(self, payload):
        response = Mock(status_code=200)
        response.json.return_value = payload
        return response

    def test_signed_get_and_paginated_fractional_no_positions(self):
        self.session.get.side_effect = [self.response({'market_positions':[
            {'ticker':'one','position_fp':'-3.65'}], 'cursor':'next'}),
            self.response({'market_positions':[{'ticker':'two','position_fp':'0.00'}]})]
        with patch('football_v2.kalshi_account.time.time', return_value=1000):
            rows = self.client.positions()
        self.assertEqual([r['ticker'] for r in rows], ['one'])
        self.assertEqual(str(quantity(rows[0])), '-3.65')
        call = self.session.get.call_args_list[1]
        self.assertEqual(call.kwargs['params']['cursor'], 'next')
        headers = call.kwargs['headers']
        self.key.public_key().verify(base64.b64decode(headers['KALSHI-ACCESS-SIGNATURE']),
            b'1000000GET/trade-api/v2/portfolio/positions',
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=32), hashes.SHA256())
        self.assertFalse(call.kwargs['allow_redirects'])

    def test_balance_cents_and_dollars(self):
        self.assertEqual(balance_values({'balance':4204,'portfolio_value':1050}), (42.04,10.50))
        self.assertEqual(balance_values({'balance_dollars':'42.0412','portfolio_value':1050}), (42.0412,10.50))

    def test_missing_and_invalid_values_are_not_zero(self):
        for row in ({}, {'position_fp':'NaN'}, {'position_fp':'infinity'}):
            with self.assertRaises(AccountError):
                quantity(row)
        with self.assertRaises(AccountError):
            balance_values({'balance':1})

    def test_http_error_is_sanitized(self):
        self.session.get.return_value = Mock(status_code=401)
        with self.assertRaisesRegex(AccountError, '^Kalshi request failed \\(HTTP 401\\)$'):
            self.client.get_balance()

    def test_repeated_cursor_fails_instead_of_partial_portfolio(self):
        self.session.get.return_value=self.response({'market_positions':[], 'cursor':'loop'})
        with self.assertRaises(AccountError):
            self.client.positions()

    def test_unsafe_ticker_never_requested(self):
        with self.assertRaises(AccountError):
            self.client.market('../orders')
        self.session.get.assert_not_called()

    def test_metadata_is_public_and_credentials_not_forwarded(self):
        self.session.get.return_value=self.response({'market':{'ticker':'KXNFLGAME-A-HOU'}})
        self.client.market('KXNFLGAME-A-HOU')
        self.assertEqual(self.session.get.call_args.kwargs['headers'], {})

    def test_missing_key_fails_without_exposing_path(self):
        with self.assertRaisesRegex(AccountError, 'credentials'):
            AccountClient('', self.path)

if __name__ == '__main__':
    unittest.main()
