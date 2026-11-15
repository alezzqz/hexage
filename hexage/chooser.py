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
from tkinter import ttk
from typing import TypeVar

from .dialog_position import show_modal
from .icon_button import pack_icon

T = TypeVar("T")


def choose(
    parent: tk.Tk | tk.Toplevel,
    title: str,
    entries: list[tuple[str, T]],
    *,
    multiple: bool = False,
) -> list[T]:
    dialog = tk.Toplevel(parent)
    dialog.withdraw()
    dialog.title(title)
    result: list[T] = []
    options = tk.Listbox(
        dialog, exportselection=False, selectmode="extended" if multiple else "browse"
    )
    options.pack(fill="both", expand=True, padx=12, pady=12)
    for label, _ in entries:
        options.insert("end", label)

    def accept(_event=None) -> None:
        result.extend(entries[index][1] for index in options.curselection())
        if result:
            dialog.destroy()

    row = ttk.Frame(dialog, padding=(12, 0, 12, 12))
    row.pack(fill="x")
    pack_icon(row, "confirm", "Подтвердить выбор", accept)
    pack_icon(row, "cancel", "Отменить выбор", dialog.destroy)
    dialog.bind("<Escape>", lambda _: dialog.destroy())
    dialog.bind("<Return>", accept)
    if not multiple:
        options.bind("<Double-Button-1>", accept)
    if show_modal(dialog, options, size=(600, 300)):
        parent.wait_window(dialog)
    return result
