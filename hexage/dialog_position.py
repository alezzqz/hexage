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

import tkinter as tk


def show_centered(
    dialog: tk.Toplevel, anchor: tk.Misc, *, size: tuple[int, int] | None = None
) -> None:
    dialog.update_idletasks()
    width, height = size or (dialog.winfo_reqwidth(), dialog.winfo_reqheight())
    # Geometry uses window-manager coordinates, including the title bar offset.
    x = anchor.winfo_x() + (anchor.winfo_width() - width) // 2
    y = anchor.winfo_y() + (anchor.winfo_height() - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    dialog.deiconify()
