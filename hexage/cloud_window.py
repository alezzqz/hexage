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
from typing import TYPE_CHECKING

from .cloud import Cloud, Snapshot
from .dialog_position import show_modal
from .icon_button import IconButton

if TYPE_CHECKING:
    from .ui import App


class CloudWindow(tk.Toplevel):
    def __init__(self, app: "App") -> None:
        super().__init__(app.root)
        self.withdraw()
        self.app = app
        self.snapshots: list[Snapshot] = []
        self.title("Облачное хранилище")
        self.minsize(550, 310)
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        self.build_provider_row(body)
        self.build_snapshot_list(body)
        self.list_status = ttk.Label(body)
        self.list_status.pack(anchor="w")
        self.build_actions(body)
        ttk.Label(body, textvariable=app.status, wraplength=515).pack(anchor="w")
        self.clear_snapshots()
        self.protocol("WM_DELETE_WINDOW", app.close_cloud_window)
        self.bind("<Escape>", lambda _: app.close_cloud_window())

    def show(self) -> None:
        show_modal(self, self.provider_combo, size=(700, 400))

    def build_snapshot_list(self, body: ttk.Frame) -> None:
        ttk.Label(body, text="Снимки · дата сохранения в облаке (UTC)").pack(anchor="w")
        panel = ttk.Frame(body)
        panel.pack(fill="both", expand=True, pady=(6, 10))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)
        self.snapshot_list = tk.Listbox(
            panel, exportselection=False, activestyle="none"
        )
        self.snapshot_list.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(panel, command=self.snapshot_list.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(
            panel, orient="horizontal", command=self.snapshot_list.xview
        )
        horizontal.grid(row=1, column=0, sticky="ew")
        self.snapshot_list.configure(
            yscrollcommand=vertical.set, xscrollcommand=horizontal.set
        )
        self.snapshot_list.bind("<<ListboxSelect>>", lambda _: self.sync_actions())

    def build_provider_row(self, body: ttk.Frame) -> None:
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(0, 12))
        ttk.Label(row, text="Провайдер").pack(side="left", padx=(0, 8))
        self.provider_combo = ttk.Combobox(
            row, values=tuple(self.app.clouds), state="readonly"
        )
        self.provider_combo.current(0)
        self.provider_combo.pack(side="left", padx=(0, 8))
        self.provider_combo.bind(
            "<<ComboboxSelected>>", lambda _: self.clear_snapshots()
        )
        self.refresh_button = self.action(
            row, "refresh", "Обновить список снимков", self.app.refresh_cloud
        )
        self.disconnect_button = self.action(
            row, "disconnect", "Отключить выбранный аккаунт", self.app.disconnect_cloud
        )

    def build_actions(self, body: ttk.Frame) -> None:
        row = ttk.Frame(body)
        row.pack(fill="x", pady=8)
        self.restore_button = self.action(
            row,
            "restore",
            "Восстановить хранилище из выбранного снимка",
            self.app.restore_cloud,
        )
        self.export_button = self.action(
            row, "cloud_export", "Экспортировать снимок в облако", self.app.export_cloud
        )
        self.delete_button = self.action(
            row,
            "delete",
            "Удалить выбранный облачный снимок",
            self.app.delete_cloud_snapshot,
        )
        self.cancel_button = self.action(
            row, "cancel", "Отменить облачную операцию", self.app.cancel_cloud
        )

    def action(
        self, row: ttk.Frame, icon: str, text: str, command: Callable[[], object]
    ) -> IconButton:
        button = IconButton(row, icon, text, command)
        button.pack(side="left", padx=(4, 0))
        return button

    def current_cloud(self) -> Cloud:
        return self.app.clouds[self.provider_combo.get()]

    def selected_snapshot(self) -> Snapshot | None:
        selected = self.snapshot_list.curselection()
        return self.snapshots[selected[0]] if selected else None

    def clear_snapshots(self) -> None:
        self.show_snapshots(
            [], "Нажмите «Обновить список снимков», чтобы загрузить список."
        )

    def show_snapshots(
        self, snapshots: list[Snapshot], empty: str = "Снимков пока нет."
    ) -> None:
        self.snapshots = snapshots
        self.snapshot_list.delete(0, "end")
        for snapshot in snapshots:
            self.snapshot_list.insert("end", snapshot.label())
        self.list_status.configure(text="" if snapshots else empty)
        self.sync_actions()

    def sync_actions(self) -> None:
        busy = self.app.job is not None
        cancel = self.app.cloud_cancel
        selected = self.selected_snapshot() is not None
        self.provider_combo.state(("disabled",) if busy else ("!disabled",))
        for button, enabled in (
            (self.refresh_button, not busy),
            (self.disconnect_button, not busy),
            (self.restore_button, selected and not busy),
            (self.export_button, self.app.session is not None and not busy),
            (self.delete_button, selected and not busy),
            (self.cancel_button, cancel is not None and not cancel.is_set()),
        ):
            button.state(("!disabled",) if enabled else ("disabled",))
