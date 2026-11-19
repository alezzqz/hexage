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

"""Run this synthetic Tk acceptance check with a graphical session."""

import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, perf_counter
from tkinter import font
from unittest.mock import patch

from hexage import ui
from hexage.chooser import choose
from hexage.cloud import EXPORT_OK, Snapshot
from hexage.cloud_window import CloudWindow
from hexage.codec import seal
from hexage.config import OAuthConfig
from hexage.dialogs import Dialog
from hexage.fonts import TEXT_FONTS, apply, legacy_fonts_message
from hexage.icon_button import IconButton
from hexage.model import Note
from hexage.session import initialize, plan_restore, save, unlock
from hexage.storage import Store
from hexage.ui import App

PASSWORD = "Синтетический тест 🔐"


def clipboard(editor):
    text = editor.text
    editor.update()
    text.focus_force()
    editor.update()
    text.tag_add("sel", "1.1", "2.2")
    assert text.bind("<Control-c>")
    assert text.bind("<Control-v>")
    editor.copy_selection()
    assert editor.clipboard_get() == "бв\n第二"
    editor.set_mode(True)
    text.tag_remove("sel", "1.0", "end")
    text.mark_set("insert", "2.0")
    editor.paste_selection()
    assert text.get("1.0", "end-1c") == "абв\nбв\n第二第二行"
    text.tag_add("sel", "1.0", "2.0")
    editor.paste_selection()
    assert text.get("1.0", "end-1c") == "бв\n第二бв\n第二第二行"
    editor.clipboard_clear()


def font_smoke() -> None:
    root = tk.Tk()
    family = apply(root)
    assert family is not None, "None of the preferred font families is installed"
    for name in TEXT_FONTS:
        assert font.nametofont(name, root=root).cget("family") == family
    fontsystem = root.tk.eval("tk::pkgconfig get fontsystem")
    if fontsystem == "xft":
        assert legacy_fonts_message(root) is None
    root.destroy()
    print(f"Fonts: {family} ({fontsystem})")


def smoke(path: Path) -> None:
    store = Store(path / "vault.hexage")
    start = perf_counter()
    session = initialize(store, PASSWORD)
    print(f"Argon2id + creation: {(perf_counter() - start) * 1000:.0f} ms")
    note = Note("2" * 32, "Unicode", "абв\n第二行")
    session = save(store, session, (note,))
    root = tk.Tk()
    app = App(root, store)
    app.activate(unlock(store, PASSWORD))
    app.list.selection_set(0)
    app.open_selected()
    editor = app.editor
    assert editor is not None
    assert root.grab_current() is editor
    clipboard(editor)
    assert editor.dirty()
    root.after(100, dismiss_modal, editor)
    editor.close()
    assert root.grab_current() is editor and editor.dirty()
    app.last_activity = monotonic() - 301
    root.after(100, app.tick)
    editor.close()
    assert app.session is None and app.editor is None
    assert not editor.winfo_exists()
    assert root.grab_current() is None
    assert unlock(store, PASSWORD).opened.vault.notes == (note,)
    incoming = replace(session.opened, vault=session.opened.vault.advance((note,)))
    restored_store = Store(path / "restored.hexage")
    plan_restore(seal(incoming), PASSWORD, None).apply(restored_store)
    assert unlock(restored_store, PASSWORD).opened.vault == incoming.vault
    print(
        f"Tk {root.tk.call('info', 'patchlevel')}: clipboard, lock, and restore passed"
    )
    close_app(app)


def close_app(app: App) -> None:
    for callback in app.root.tk.call("after", "info"):
        app.root.after_cancel(callback)
    app.close()


def note_list_smoke(path: Path) -> None:
    store = Store(path / "note-list.hexage")
    notes = (
        Note("1" * 32, "Яблоко", "Синтетический текст"),
        Note("2" * 32, "Бета", ""),
        Note("3" * 32, "альфа БЕТА", ""),
    )
    session = save(store, initialize(store, PASSWORD), notes)
    root = tk.Tk()
    app = App(root, store)
    app.activate(session)
    assert app.list.get(0, "end") == (notes[2].title, notes[1].title, notes[0].title)
    app.list.selection_set(1)
    app.filter_text.set("бЕт")
    assert app.list.get(0, "end") == (notes[2].title, notes[1].title)
    assert app.list.curselection() == (1,)
    with patch.object(app, "edit") as edit:
        app.open_selected()
        edit.assert_called_once_with(notes[1])
    app.filter_text.set("нет совпадений")
    assert app.list.size() == 0
    app.filter_text.set("")
    assert app.list.size() == 3
    app.lock(force=True)
    assert app.visible_notes == () and app.filter_text.get() == ""
    app.activate(session)
    assert app.list.size() == 3
    close_app(app)
    print("Note sorting, live title filtering, selection, and lock clearing passed")


def dismiss_modal(owner: tk.Tk | tk.Toplevel) -> None:
    dialog = owner.grab_current()
    assert isinstance(dialog, tk.Toplevel) and dialog.master is owner
    dialog.destroy()


def cloud_export_smoke(app: App, window: CloudWindow) -> None:
    session = initialize(app.store, PASSWORD)
    app.activate(session)
    combo = window.provider_combo
    assert combo.instate(("readonly",))
    assert window.current_cloud().provider.name == "Google Drive"
    window.show_snapshots([Snapshot("synthetic", "synthetic.hexage", "")])
    combo.current(1)
    combo.event_generate("<<ComboboxSelected>>")
    assert window.snapshot_list.size() == 0
    cloud = window.current_cloud()
    assert cloud.provider.name == "Яндекс Диск"
    cancel = Event()
    with (
        patch.object(app, "run_cloud") as run_cloud,
        patch.object(
            ui, "export_to", return_value={cloud.provider.name: EXPORT_OK}
        ) as export,
        patch.object(ui.dialogs, "show_message"),
        patch.object(app, "refresh_cloud") as refresh,
    ):
        window.export_button.invoke()
        run_cloud.assert_called_once()
        assert app.root.grab_current() is window
        operation, done = run_cloud.call_args.args
        done(operation(cancel))
        export.assert_called_once_with(
            (cloud,), app.store.snapshot(session.digest), cancel
        )
        refresh.assert_called_once_with()


def modal_smoke(path: Path) -> None:
    root = tk.Tk()
    app = App(
        root,
        Store(path / "modal.hexage"),
        OAuthConfig(google_client_id="test", yandex_client_id="test"),
    )
    root.update()
    app.show_about()
    assert root.grab_current() is not None
    app.close()
    assert root.winfo_exists()
    dismiss_modal(root)
    assert root.grab_current() is None
    app.open_cloud_window()
    window = app.cloud_window
    assert window is not None and root.grab_current() is window
    root.update_idletasks()
    assert window.winfo_height() >= window.winfo_reqheight(), (
        "Cloud window must open tall enough for its action buttons"
    )
    cloud_export_smoke(app, window)
    root.after(100, dismiss_modal, window)
    assert choose(window, "Тест", [("Пункт", 1)]) == []
    assert root.grab_current() is window
    app.close_cloud_window()
    assert root.grab_current() is None
    close_app(app)
    print("Modal windows and nested grab restoration passed")


def startup_smoke(path: Path) -> None:
    root = tk.Tk()
    visible = []

    def observe() -> None:
        dialog = next(
            (child for child in root.winfo_children() if isinstance(child, Dialog)),
            None,
        )
        visible.append(
            bool(root.winfo_viewable() and dialog and dialog.winfo_viewable())
        )
        if dialog:
            dialog.destroy()
        root.after_idle(root.destroy)

    root.after(500, observe)
    with (
        patch.object(ui.tk, "Tk", return_value=root),
        patch.object(ui, "config_path", return_value=path / "hexage.yaml"),
        patch.object(ui, "default_path", return_value=path / "vault.hexage"),
    ):
        ui.main()
    assert visible == [True], "Startup password dialog and main window must be visible"
    assert (path / "hexage.yaml").exists(), "First run must create the config file"
    print("Startup password dialog passed")


def wait_for_tooltip(root: tk.Tk) -> None:
    done = tk.BooleanVar(root)
    root.after(500, done.set, True)
    root.wait_variable(done)


def tooltip_smoke(path: Path) -> None:
    root = tk.Tk()
    app = App(root, Store(path / "tooltip.hexage"))
    root.update()
    about = next(
        button
        for button in app.toolbar.winfo_children()
        if isinstance(button, IconButton) and button.cget("text") == "О программе"
    )
    about.focus_force()
    root.update()
    with patch.object(about, "winfo_pointerxy") as pointer:
        pointer.return_value = (about.winfo_rootx() + 2, about.winfo_rooty() + 2)
        about.event_generate("<Enter>")
        wait_for_tooltip(root)
        assert about._tip is not None
        about.invoke()
        root.update()
        assert about._tip is None
        pointer.return_value = (root.winfo_rootx() + 300, root.winfo_rooty() + 200)
        dismiss_modal(root)
        about.event_generate("<Enter>")  # Tk can send a crossing event on grab release.
        wait_for_tooltip(root)
        assert about._tip is None
        root.tk.call("tk::TabToWindow", about)
        wait_for_tooltip(root)
        assert about._tip is not None
    close_app(app)
    print("Tooltip hover, modal close, and keyboard traversal passed")


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        smoke(Path(directory))
        note_list_smoke(Path(directory))
        modal_smoke(Path(directory))
        startup_smoke(Path(directory))
        tooltip_smoke(Path(directory))
        font_smoke()
