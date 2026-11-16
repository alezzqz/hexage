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

"""Choose one Tk text family that covers both Latin and Cyrillic."""

import sys
import tkinter as tk
from collections.abc import Iterable
from tkinter import font

# Families shipped with the target platforms or common Linux desktops. The
# legacy X11 names are last so they are used only when nothing better exists.
PREFERRED_FAMILIES = (
    "Segoe UI",
    "SF Pro Text",
    "Helvetica Neue",
    "DejaVu Sans",
    "Noto Sans",
    "Liberation Sans",
    "Ubuntu",
    "Cantarell",
    "FreeSans",
    "Arial",
    "Tahoma",
    "Verdana",
    "Nimbus Sans L",
    "Nimbus Sans",
    "Helvetica",
)

# Tk widgets read these named fonts by default; TkFixedFont stays monospace.
TEXT_FONTS = (
    "TkDefaultFont",
    "TkTextFont",
    "TkMenuFont",
    "TkHeadingFont",
    "TkCaptionFont",
    "TkSmallCaptionFont",
    "TkIconFont",
    "TkTooltipFont",
)


def choose_family(available: Iterable[str]) -> str | None:
    """Return the first preferred family present in the platform family list."""
    names = {name.casefold(): name for name in available}
    return next(
        (
            names[wanted.casefold()]
            for wanted in PREFERRED_FAMILIES
            if wanted.casefold() in names
        ),
        None,
    )


def apply(root: tk.Misc) -> str | None:
    """Use one family for all text so Latin and Cyrillic do not mix fonts."""
    family = choose_family(font.families(root))
    if family is None:
        return None
    for name in TEXT_FONTS:
        try:
            named = font.nametofont(name, root=root)
        except tk.TclError:
            continue
        named.configure(family=family)
    return family


def legacy_fonts_message(root: tk.Misc) -> str | None:
    """Warn when Tk cannot see system TrueType fonts and uses X11 fallbacks."""
    if sys.platform != "linux":
        return None
    try:
        fontsystem = str(root.tk.eval("tk::pkgconfig get fontsystem"))
    except tk.TclError:
        return None
    if fontsystem == "xft":
        return None
    return (
        "Hexage: this Tk build has no Xft support, so it uses legacy X11 fonts. "
        "Install Tk with Xft support (python3-tk on Debian/Ubuntu) and use a "
        "Python built against it."
    )
