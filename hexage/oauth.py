# Copyright (C) 2026 TermoGRAF
# SPDX-License-Identifier: LGPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License and
# the GNU General Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

import base64
import hashlib
import json
import os
import secrets
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event
from time import monotonic, time
from urllib.parse import parse_qs, urlencode, urlsplit

import keyring

from .config import OAuthConfig
from .http import request
from .model import HexageError


@dataclass(frozen=True, repr=False)
class Provider:
    name: str
    client_id: str
    authorize_url: str
    token_url: str
    scope: str
    port: int
    path: str
    client_secret: str = ""

    @property
    def credential(self) -> str:
        return f"{self.name}:{self.client_id}"


def providers(config: OAuthConfig) -> dict[str, Provider]:
    google = Provider(
        "Google Drive",
        config.google_client_id,
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/auth/drive.appdata",
        0,
        "/",
        config.google_client_secret,
    )
    yandex = Provider(
        "Яндекс Диск",
        config.yandex_client_id,
        "https://oauth.yandex.ru/authorize",
        "https://oauth.yandex.ru/token",
        "cloud_api:disk.app_folder",
        43857,
        "/oauth",
    )
    return {
        provider.name: provider for provider in (google, yandex) if provider.client_id
    }


def check_cancel(cancel: Event) -> None:
    if cancel.is_set():
        raise HexageError("Операция отменена.")


class CallbackServer(HTTPServer):
    def __init__(self, provider: Provider, state: str) -> None:
        super().__init__(("127.0.0.1", provider.port), Callback)
        self.timeout = 0.25
        self.path = provider.path
        self.state = state
        self.result: str | None = None

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(2)
        return connection, address

    def handle_error(self, _request, _address) -> None:
        pass


class Callback(BaseHTTPRequestHandler):
    server: CallbackServer

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        values = (
            parse_qs(url.query, max_num_fields=32) if url.query.count("&") < 32 else {}
        )
        state = values.get("state", [])
        good = (
            url.path == self.server.path
            and len(state) == 1
            and state[0].isascii()
            and secrets.compare_digest(state[0], self.server.state)
        )
        if good:
            codes = values.get("code", [])
            self.server.result = (
                codes[0] if len(codes) == 1 and "error" not in values else ""
            )
        self.send_response(200 if good else 400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b"Return to Hexage." if good else b"Invalid callback.")

    def log_message(self, *_args) -> None:
        pass


def authorize(provider: Provider, cancel: Event) -> dict:
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    check_cancel(cancel)
    with CallbackServer(provider, state) as server:
        redirect = f"http://127.0.0.1:{server.server_port}{provider.path}"
        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": provider.scope,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if provider.name == "Google Drive":
            params.update(access_type="offline", prompt="consent")
        if not webbrowser.open(f"{provider.authorize_url}?{urlencode(params)}"):
            raise HexageError("Не удалось открыть системный браузер.")
        deadline = monotonic() + 180
        while server.result is None and monotonic() < deadline:
            check_cancel(cancel)
            server.handle_request()
        code = server.result
    if not code:
        raise HexageError("Авторизация отклонена или истекло время ожидания.")
    return token_request(
        provider,
        cancel,
        grant_type="authorization_code",
        code=code,
        redirect_uri=redirect,
        code_verifier=verifier,
    )


def token_request(provider: Provider, cancel: Event, **form: str) -> dict:
    form["client_id"] = provider.client_id
    if provider.client_secret:
        form["client_secret"] = provider.client_secret
    result = request("POST", provider.token_url, cancel, data=form, limit=65536)
    if not isinstance(result.get("access_token"), str) or not result["access_token"]:
        raise HexageError("Провайдер не вернул токен доступа.")
    return result


def system_keyring():
    try:
        if os.name == "nt":
            from keyring.backends.Windows import WinVaultKeyring

            return WinVaultKeyring()
        if os.name == "posix":
            from keyring.backends.SecretService import Keyring

            return Keyring()
    except Exception:
        pass
    return None


class Credentials:
    def __init__(self) -> None:
        self.cached: dict[str, tuple[str, float]] = {}
        self.refresh: dict[str, str] = {}
        self.backend: keyring.backend.KeyringBackend | None = None
        self.disabled: set[str] = set()

    def access(self, provider: Provider, cancel: Event) -> str:
        key = provider.credential
        token, expires = self.cached.get(key, ("", 0))
        if monotonic() < expires:
            return token
        stored = self.load_refresh(key)
        google = provider.name == "Google Drive"
        if stored and not google:
            token = self.yandex_access(key, stored)
            if token:
                return token
        refresh = stored if google else None
        if refresh:
            try:
                result = token_request(
                    provider, cancel, grant_type="refresh_token", refresh_token=refresh
                )
            except HexageError as error:
                if getattr(error, "status", None) not in {400, 401}:
                    raise
                self.disconnect(provider)
                result = authorize(provider, cancel)
        else:
            result = authorize(provider, cancel)
        token = result["access_token"]
        ttl = max(0, int(result.get("expires_in", 3600)) - 30)
        self.cached[key] = (token, monotonic() + ttl)
        if google and isinstance(result.get("refresh_token"), str):
            self.save_refresh(key, result["refresh_token"])
        elif not google:
            self.save_refresh(key, json.dumps([token, time() + ttl]))
        return token

    def yandex_access(self, key: str, stored: str) -> str | None:
        try:
            token, expiry = json.loads(stored)
            remaining = expiry - time()
        except (ValueError, TypeError):
            return None
        if isinstance(token, str) and remaining > 0:
            self.cached[key] = (token, monotonic() + remaining)
            return token
        return None

    def load_refresh(self, key: str) -> str | None:
        if key in self.refresh or key in self.disabled:
            return self.refresh.get(key)
        try:
            self.backend = self.backend or system_keyring()
            if self.backend:
                return self.backend.get_password("Hexage", key)
        except Exception:
            pass
        return None

    def save_refresh(self, key: str, token: str) -> None:
        self.disabled.discard(key)
        self.refresh[key] = token
        try:
            self.backend = self.backend or system_keyring()
            if self.backend:
                self.backend.set_password("Hexage", key, token)
        except Exception:
            pass

    def disconnect(self, provider: Provider, *, strict: bool = False) -> None:
        key = provider.credential
        self.cached.pop(key, None)
        self.refresh.pop(key, None)
        self.disabled.add(key)
        self.backend = self.backend or system_keyring()
        try:
            if self.backend and self.backend.get_password("Hexage", key) is not None:
                self.backend.delete_password("Hexage", key)
        except Exception:
            if strict:
                raise HexageError(
                    "Не удалось удалить токен из системного хранилища."
                ) from None
