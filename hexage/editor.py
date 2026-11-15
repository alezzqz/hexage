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
from collections.abc import Callable
from tkinter import ttk

from . import dialogs
from .dialog_position import has_modal_child, show_modal
from .icon_button import pack_icon
from .model import Note, identifier


class Editor(tk.Toplevel):
    def __init__(self, parent: tk.Tk, note: Note | None, save: Callable) -> None:
        super().__init__(parent)
        self.withdraw()
        self.clipboard_owner = parent
        self.note = note
        self.save_note = save
        self.title("Заметка")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.name = ttk.Entry(self)
        self.name.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=12)
        self.text = tk.Text(
            self, font="TkTextFont", wrap="word", undo=True, exportselection=False
        )
        self.text.grid(row=1, column=0, sticky="nsew", padx=(12, 0))
        scroll = ttk.Scrollbar(self, command=self.text.yview)
        scroll.grid(row=1, column=1, sticky="ns", padx=(0, 12))
        self.text.configure(yscrollcommand=scroll.set)
        self.controls = ttk.Frame(self)
        self.controls.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=12)
        self.editing = note is None
        if note:
            self.name.insert(0, note.title)
            self.text.insert("1.0", note.text)
        self.set_mode(self.editing)
        self.text.bind("<Control-c>", self.copy_selection)
        self.text.bind("<Control-v>", self.paste_selection)
        self.text.bind("<Button-3>", self.context_menu)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Копировать", command=self.copy_selection)
        self.menu.add_command(label="Вставить", command=self.paste_selection)

    def show(self) -> None:
        show_modal(self, self.name if self.editing else self.text, size=(640, 480))

    def set_mode(self, editing: bool) -> None:
        self.editing = editing
        self.name.configure(state="normal" if editing else "readonly")
        self.text.configure(state="normal" if editing else "disabled")
        for child in self.controls.winfo_children():
            child.destroy()
        if editing:
            pack_icon(self.controls, "save", "Сохранить заметку", self.submit)
            pack_icon(self.controls, "cancel", "Отменить редактирование", self.close)
        else:
            pack_icon(
                self.controls,
                "edit",
                "Редактировать заметку",
                lambda: self.set_mode(True),
            )
            pack_icon(
                self.controls,
                "copy",
                "Копировать выделенный текст (Ctrl+C)",
                self.copy_selection,
            )

    def dirty(self) -> bool:
        original = (self.note.title, self.note.text) if self.note else ("", "")
        return (self.name.get(), self.text.get("1.0", "end-1c")) != original

    def submit(self) -> None:
        note = Note(
            self.note.id if self.note else identifier(),
            self.name.get(),
            self.text.get("1.0", "end-1c"),
        )
        self.save_note(self, note)

    def close(self) -> None:
        if has_modal_child(self):
            return
        if not self.dirty() or dialogs.ask_yes_no(
            "Несохранённые изменения",
            "Закрыть и отбросить правки?",
            parent=self,
        ):
            self.destroy()

    def copy_selection(self, _event: tk.Event | None = None) -> str:
        if self.text.tag_ranges("sel"):
            self.clipboard_owner.clipboard_clear()
            self.clipboard_owner.clipboard_append(
                self.text.get("sel.first", "sel.last")
            )
        return "break"

    def paste_selection(self, _event: tk.Event | None = None) -> str:
        if self.text.cget("state") == "normal":
            try:
                value = self.clipboard_owner.clipboard_get()
            except tk.TclError:
                return "break"
            if self.text.tag_ranges("sel"):
                self.text.replace("sel.first", "sel.last", value)
            else:
                self.text.insert("insert", value)
        return "break"

    def context_menu(self, event: tk.Event) -> None:
        self.menu.entryconfigure(1, state="normal" if self.editing else "disabled")
        # Tk restores the editor's grab when the popup closes.
        self.menu.tk_popup(event.x_root, event.y_root)
