"""Restricted GET-only Kalshi account access. Never log requests or credentials."""
from __future__ import annotations

import base64
import os
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests

BASE_URL = 'https://external-api.kalshi.com/trade-api/v2'


class AccountError(RuntimeError):
    """A message safe to show in Telegram or a service log."""


def decimal_value(value) -> Decimal:
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise InvalidOperation
        return number
    except (InvalidOperation, ValueError, TypeError):
        raise AccountError('Kalshi returned an invalid numeric value') from None


def quantity(row: dict) -> Decimal:
    return decimal_value(row.get('position_fp', row.get('position')))


def balance_values(row: dict) -> tuple[float, float]:
    cash = (decimal_value(row['balance_dollars']) if row.get('balance_dollars') is not None
            else decimal_value(row.get('balance')) / 100)
    positions = decimal_value(row.get('portfolio_value')) / 100
    return float(cash), float(positions)


class AccountClient:
    def __init__(self, key_id: str, key_path: Path, *, session=None, timeout=20):
        if not key_id or any(c.isspace() for c in key_id):
            raise AccountError('Missing or invalid Kalshi credentials')
        self.key_id, self.timeout = key_id, timeout
        self.session = session or requests.Session()
        try:
            from cryptography.hazmat.primitives import serialization
            if os.name == 'posix' and key_path.stat().st_mode & 0o077:
                raise AccountError('Kalshi private key must have owner-only permissions')
            self.key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
            if not isinstance(self.key, RSAPrivateKey):
                raise AccountError('Kalshi reporting requires the configured RSA key')
        except AccountError:
            raise
        except Exception:
            raise AccountError('Cannot load Kalshi private key; check configuration and cryptography') from None

    @classmethod
    def from_env(cls):
        # Importing settings loads the established central env, not a new config source.
        from football_v2.config import settings
        path = os.getenv('KALSHI_PRIVATE_KEY_PATH', '').strip()
        if not path:
            raise AccountError('Missing Kalshi credentials in central env')
        return cls(os.getenv('KALSHI_API_KEY_ID', '').strip(), Path(path), timeout=settings.request_timeout)

    def _get(self, path: str, params=None, *, signed=False) -> dict:
        # There is deliberately no generic HTTP method or configurable host.
        headers = {}
        if signed:
            if path not in ('/portfolio/balance', '/portfolio/positions'):
                raise AccountError('Unsupported Kalshi account read')
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            stamp = str(int(time.time() * 1000))
            signature = self.key.sign((stamp + 'GET/trade-api/v2' + path).encode(),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
            headers = {'KALSHI-ACCESS-KEY': self.key_id, 'KALSHI-ACCESS-TIMESTAMP': stamp,
                       'KALSHI-ACCESS-SIGNATURE': base64.b64encode(signature).decode()}
        try:
            response = self.session.get(BASE_URL + path, params=params or {}, headers=headers,
                timeout=self.timeout, allow_redirects=False)
            if response.status_code != 200:
                raise AccountError(f'Kalshi request failed (HTTP {response.status_code})')
            payload = response.json()
            if not isinstance(payload, dict):
                raise AccountError('Kalshi returned an invalid response')
            return payload
        except AccountError:
            raise
        except Exception:
            raise AccountError('Kalshi request failed; try again later') from None

    def get_balance(self) -> dict:
        result = self._get('/portfolio/balance', signed=True)
        balance_values(result)
        return result

    def positions(self) -> list[dict]:
        rows, cursor, seen = [], '', set()
        for _ in range(100):
            payload = self._get('/portfolio/positions',
                {'limit':100, **({'cursor':cursor} if cursor else {})}, signed=True)
            page = payload.get('market_positions')
            if not isinstance(page, list):
                raise AccountError('Kalshi returned invalid positions')
            rows.extend(row for row in page if quantity(row) != 0)
            cursor = payload.get('cursor', '')
            if not cursor:
                return rows
            if cursor in seen:
                break
            seen.add(cursor)
        raise AccountError('Kalshi positions incomplete; pagination did not finish')

    def _metadata(self, kind: str, ticker: str) -> dict:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', ticker):
            raise AccountError('Invalid Kalshi ticker')
        row = self._get(f'/{kind}s/{ticker}').get(kind)
        if not isinstance(row, dict):
            raise AccountError('Kalshi market description unavailable')
        return row

    def market(self, ticker: str) -> dict:
        return self._metadata('market', ticker)

    def event(self, ticker: str) -> dict:
        return self._metadata('event', ticker)
