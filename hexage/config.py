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

from dataclasses import dataclass
from pathlib import Path

import yaml
from platformdirs import user_config_path

from .model import HexageError

MAX_CONFIG_BYTES = 64 * 1024

DEFAULT_CONFIG = """\
# Hexage создаёт этот файл автоматически при первом запуске.
# Впишите Client ID приложений OAuth и перезапустите Hexage.
oauth:
  google:
    client_id: ""
    # Заполните, если Google требует Client secret.
    client_secret: ""
  yandex:
    client_id: ""
"""


@dataclass(frozen=True, repr=False)
class OAuthConfig:
    google_client_id: str = ""
    google_client_secret: str = ""
    yandex_client_id: str = ""


def config_path() -> Path:
    return user_config_path("Hexage", appauthor=False) / "hexage.yaml"


def ensure_config(path: Path) -> None:
    """Create the default config on first run without overwriting user edits."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise HexageError("Не удалось создать hexage.yaml.") from None
    try:
        with path.open("x", encoding="utf-8", newline="\n") as target:
            target.write(DEFAULT_CONFIG)
    except FileExistsError:
        return
    except OSError:
        raise HexageError("Не удалось создать hexage.yaml.") from None


def mapping(value: object, location: str, allowed: set[str]) -> dict:
    if not isinstance(value, dict) or value.keys() - allowed:
        raise HexageError(f"Проверьте поля раздела {location} в hexage.yaml.")
    return value


def field(values: dict, key: str, location: str) -> str:
    value = values.get(key, "")
    if not isinstance(value, str):
        raise HexageError(f"Поле {location}.{key} в hexage.yaml должно быть строкой.")
    return value.strip()


def load_oauth_config(path: Path) -> OAuthConfig:
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_CONFIG_BYTES + 1)
    except FileNotFoundError:
        return OAuthConfig()
    except OSError:
        raise HexageError("Не удалось прочитать hexage.yaml.") from None
    if len(raw) > MAX_CONFIG_BYTES:
        raise HexageError("Размер hexage.yaml превышает 64 КиБ.")
    try:
        value = yaml.safe_load(raw.decode("utf-8-sig"))
    except (yaml.YAMLError, UnicodeError, ValueError, RecursionError):
        raise HexageError(
            "Не удалось разобрать hexage.yaml. Проверьте YAML и UTF-8."
        ) from None
    root = mapping({} if value is None else value, "верхнего уровня", {"oauth"})
    oauth = mapping(root.get("oauth", {}), "oauth", {"google", "yandex"})
    google = mapping(
        oauth.get("google", {}), "oauth.google", {"client_id", "client_secret"}
    )
    yandex = mapping(oauth.get("yandex", {}), "oauth.yandex", {"client_id"})
    google_id = field(google, "client_id", "oauth.google")
    google_secret = field(google, "client_secret", "oauth.google")
    if google_secret and not google_id:
        raise HexageError("Укажите oauth.google.client_id в hexage.yaml.")
    return OAuthConfig(
        google_id, google_secret, field(yandex, "client_id", "oauth.yandex")
    )
