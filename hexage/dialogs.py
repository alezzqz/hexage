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

from .dialog_position import show_modal


class Dialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk | tk.Toplevel, title: str, message: str) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.resizable(False, False)
        self.result: str | None = None
        self.body = ttk.Frame(self, padding=16)
        self.body.pack(fill="both", expand=True)
        ttk.Label(self.body, text=message, wraplength=440, justify="left").pack(
            fill="x", pady=(0, 12)
        )
        self.bind("<Escape>", lambda _: self.destroy())

    def finish(self, value: str) -> None:
        self.result = value
        self.destroy()

    def wait_for_result(self, focus: tk.Widget) -> str | None:
        if show_modal(self, focus):
            self.wait_window()
        return self.result


def ask_yes_no(title: str, message: str, *, parent: tk.Tk | tk.Toplevel) -> bool:
    dialog = Dialog(parent, title, message)
    row = ttk.Frame(dialog.body)
    row.pack(anchor="e")
    yes = ttk.Button(row, text="Да", command=lambda: dialog.finish("yes"))
    yes.pack(side="left", padx=(0, 8))
    no = ttk.Button(row, text="Нет", command=dialog.destroy)
    no.pack(side="left")
    yes.bind("<Return>", lambda _: yes.invoke())
    no.bind("<Return>", lambda _: no.invoke())
    return dialog.wait_for_result(no) == "yes"


def show_message(title: str, message: str, *, parent: tk.Tk | tk.Toplevel) -> None:
    dialog = Dialog(parent, title, message)
    button = ttk.Button(dialog.body, text="OK", command=dialog.destroy)
    button.pack(anchor="e")
    dialog.bind("<Return>", lambda _: dialog.destroy())
    dialog.wait_for_result(button)


def ask_password(prompt: str, *, parent: tk.Tk | tk.Toplevel) -> str | None:
    dialog = Dialog(parent, "Hexage", prompt)
    entry = ttk.Entry(dialog.body, show="•", width=36)
    entry.pack(fill="x", pady=(0, 12))
    row = ttk.Frame(dialog.body)
    row.pack(anchor="e")
    submit = ttk.Button(row, text="OK", command=lambda: dialog.finish(entry.get()))
    submit.pack(side="left", padx=(0, 8))
    cancel = ttk.Button(row, text="Отмена", command=dialog.destroy)
    cancel.pack(side="left")
    entry.bind("<Return>", lambda _: submit.invoke())
    submit.bind("<Return>", lambda _: submit.invoke())
    cancel.bind("<Return>", lambda _: cancel.invoke())
    return dialog.wait_for_result(entry)
