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

import pytest

from hexage.config import OAuthConfig, ensure_config, load_oauth_config
from hexage.model import HexageError
from hexage.oauth import providers


def test_first_run_creates_default_config(tmp_path):
    path = tmp_path / "Hexage" / "hexage.yaml"
    ensure_config(path)
    assert path.exists()
    assert load_oauth_config(path) == OAuthConfig()
    assert "client_id" in path.read_text(encoding="utf-8")


def test_existing_config_is_not_overwritten(tmp_path):
    path = tmp_path / "hexage.yaml"
    original = 'oauth: {google: {client_id: "sample"}}\n'
    path.write_text(original, encoding="utf-8")
    ensure_config(path)
    assert path.read_text(encoding="utf-8") == original
    assert load_oauth_config(path).google_client_id == "sample"


def test_missing_config_works_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("HEXAGE_GOOGLE_CLIENT_ID", "obsolete")
    assert providers(load_oauth_config(tmp_path / "hexage.yaml")) == {}


def test_load_config_and_create_providers(tmp_path):
    path = tmp_path / "hexage.yaml"
    path.write_text(
        'oauth:\n  google:\n    client_id: "google-id"\n    client_secret: "sample"\n'
        '  yandex:\n    client_id: "012345"\n',
        encoding="utf-8-sig",
    )
    settings = providers(load_oauth_config(path))
    assert settings["Google Drive"].client_id == "google-id"
    assert settings["Google Drive"].client_secret == "sample"
    assert settings["Яндекс Диск"].client_id == "012345"
    assert settings["Яндекс Диск"].client_secret == ""


@pytest.mark.parametrize("text", ["", "oauth: {}", 'oauth: {google: {client_id: ""}}'])
def test_empty_config(tmp_path, text):
    path = tmp_path / "hexage.yaml"
    path.write_text(text, encoding="utf-8")
    assert load_oauth_config(path) == OAuthConfig()


@pytest.mark.parametrize(
    "text",
    [
        "oauth: [",
        "oauth: {yandex: {client_id: 123}}",
        "oauth: {google: {client_secret: synthetic}}",
        "oauth: {yandex: {token: synthetic}}",
        "!!python/name:builtins.print",
    ],
)
def test_invalid_config_reports_safe_error(tmp_path, text):
    path = tmp_path / "hexage.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(HexageError, match="hexage.yaml") as error:
        load_oauth_config(path)
    assert "synthetic" not in str(error.value)
