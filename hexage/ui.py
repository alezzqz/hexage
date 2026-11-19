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

import sys
import tkinter as tk
import webbrowser
from concurrent.futures import Future, ThreadPoolExecutor
from importlib.resources import files
from pathlib import Path
from threading import Event
from time import monotonic
from tkinter import filedialog, font, ttk

from . import dialogs, fonts
from .chooser import choose
from .cloud import EXPORT_OK, Cloud, Snapshot, export_to
from .cloud_window import CloudWindow
from .config import OAuthConfig, config_path, ensure_config, load_oauth_config
from .dialog_position import has_modal_child, show_modal
from .editor import Editor
from .icon_button import pack_icon
from .model import HexageError, Note
from .oauth import Credentials, providers
from .session import (
    RestorePlan,
    Session,
    change_password,
    initialize,
    plan_restore,
    save,
    unlock,
)
from .storage import Store, default_path, read_file

FILES = [("Снимки Hexage", "*.hexage"), ("Все файлы", "*")]


class App:
    def __init__(
        self, root: tk.Tk, store: Store, config: OAuthConfig = OAuthConfig()
    ) -> None:
        self.root, self.store = root, store
        self.session: Session | None = None
        self.visible_notes: tuple[Note, ...] = ()
        self.filter_text = tk.StringVar(root)
        self.filter_text.trace_add("write", self.refresh_notes)
        self.editor: Editor | None = None
        self.job: Future | None = None
        self.generation = 0
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.last_activity = monotonic()
        credentials = Credentials()
        self.clouds = {
            name: Cloud(p, credentials) for name, p in providers(config).items()
        }
        self.cloud_cancel: Event | None = None
        self.cloud_window: CloudWindow | None = None
        default_font = font.nametofont("TkDefaultFont", root=root)
        self.app_heading = default_font.copy()
        self.app_heading.configure(size=24, weight="bold")
        self.about_heading = default_font.copy()
        self.about_heading.configure(size=16, weight="bold")
        root.title("Hexage")
        root.geometry("680x480")
        root.minsize(max(480, round(root.winfo_fpixels("360p"))), 330)
        self.frame = ttk.Frame(root, padding=18)
        self.frame.pack(fill="both", expand=True)
        self.toolbar = ttk.Frame(self.frame)
        self.status = tk.StringVar()
        footer = ttk.Frame(root, padding=(18, 4))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status).pack(side="left")
        ttk.Sizegrip(root).place(relx=1.0, rely=1.0, anchor="se")
        for event in ("<KeyPress>", "<ButtonPress>", "<Motion>", "<MouseWheel>"):
            root.bind_all(event, self.activity, add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(300, self.tick)
        self.render()

    def activity(self, _event: tk.Event | None = None) -> None:
        self.last_activity = monotonic()

    def tick(self) -> None:
        if self.session and monotonic() - self.last_activity >= 300:
            self.lock(force=True)
        self.root.after(300, self.tick)

    def render(self) -> None:
        self.toolbar.pack_forget()
        for child in self.toolbar.winfo_children():
            child.destroy()
        for child in self.frame.winfo_children():
            if child is not self.toolbar:
                child.destroy()
        if self.session:
            self.render_notes()
        else:
            self.render_locked()
        pack_icon(self.toolbar, "info", "О программе", self.show_about)

    def show_about(self) -> None:
        if not self.available():
            return
        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title("О программе")
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=18)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Hexage", font=self.about_heading).pack(anchor="w")
        ttk.Label(body, text="Зашифрованные заметки").pack(anchor="w", pady=(4, 0))
        ttk.Label(body, text="© 2026 TermoGRAF").pack(anchor="w", pady=(4, 0))
        ttk.Label(body, text="Версия 1.1").pack(anchor="w", pady=(0, 6))
        ttk.Label(body, text="Лицензия: GNU LGPL v3 или новее").pack(anchor="w")
        license_link = ttk.Button(
            body,
            text="Текст лицензии: gnu.org/licenses/lgpl-3.0",
            command=lambda: webbrowser.open(
                "https://www.gnu.org/licenses/lgpl-3.0.html"
            ),
        )
        license_link.pack(anchor="w", pady=(0, 6))
        link = ttk.Button(
            body,
            text="Иконки: Icons8 · icons8.com",
            command=lambda: webbrowser.open("https://icons8.com"),
        )
        link.pack(anchor="w")
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        show_modal(dialog, license_link)

    def needs_setup(self) -> bool:
        try:
            self.store.path.lstat()
        except FileNotFoundError:
            return True
        except OSError:
            # An inaccessible vault should still go through the unlock flow.
            return False
        return False

    def render_locked(self) -> None:
        ttk.Label(self.frame, text="Hexage", font=self.app_heading).pack(anchor="w")
        row = self.toolbar
        row.pack(anchor="w", pady=16)
        if self.needs_setup():
            pack_icon(row, "create", "Создать хранилище", self.create)
            pack_icon(
                row,
                "restore",
                "Восстановить из локального файла",
                self.restore_file,
            )
            if self.clouds:
                pack_icon(row, "cloud", "Облачное хранилище", self.open_cloud_window)
        else:
            pack_icon(row, "unlock", "Разблокировать хранилище", self.unlock)

    def render_notes(self) -> None:
        self.toolbar.pack(fill="x", pady=(0, 12))
        self.render_note_actions()
        search = ttk.Frame(self.frame)
        search.pack(fill="x", pady=(0, 8))
        ttk.Label(search, text="Фильтр по названию:").pack(side="left", padx=(0, 8))
        filter_entry = ttk.Entry(search, textvariable=self.filter_text)
        filter_entry.pack(fill="x", expand=True)
        filter_entry.focus_set()
        notes_frame = ttk.Frame(self.frame)
        notes_frame.pack(fill="both", expand=True)
        self.list = tk.Listbox(
            notes_frame, selectmode="extended", exportselection=False
        )
        scrollbar = ttk.Scrollbar(
            notes_frame, orient="vertical", command=self.list.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.list.pack(side="left", fill="both", expand=True)
        self.list.configure(yscrollcommand=scrollbar.set)
        self.refresh_notes()
        self.list.bind("<Double-Button-1>", lambda _: self.open_selected())
        self.list.bind("<Return>", lambda _: self.open_selected())
        ttk.Label(
            self.frame, text="Через 5 минут бездействия правки будут отброшены."
        ).pack(anchor="w", pady=(8, 0))

    def refresh_notes(self, *_trace_args: str) -> None:
        if self.session is None:
            return
        selected = {self.visible_notes[i].id for i in self.list.curselection()}
        query = self.filter_text.get().casefold()
        self.visible_notes = tuple(
            sorted(
                (
                    n
                    for n in self.session.opened.vault.notes
                    if query in n.title.casefold()
                ),
                key=lambda n: n.title.casefold().replace("ё", "е"),
            )
        )
        self.list.delete(0, "end")
        for index, note in enumerate(self.visible_notes):
            self.list.insert("end", note.title)
            if note.id in selected:
                self.list.selection_set(index)

    def render_note_actions(self) -> None:
        row = self.toolbar
        pack_icon(row, "new", "Создать заметку", lambda: self.edit(None))
        pack_icon(row, "open", "Открыть выбранную заметку", self.open_selected)
        pack_icon(row, "delete", "Удалить выбранные заметки", self.delete)
        pack_icon(row, "lock", "Заблокировать хранилище", self.lock)
        pack_icon(row, "export", "Экспортировать в локальный файл", self.export)
        pack_icon(
            row,
            "restore",
            "Восстановить из локального файла",
            self.restore_file,
        )
        pack_icon(row, "key", "Сменить пароль", self.change_password)
        if self.clouds:
            pack_icon(row, "cloud", "Облачное хранилище", self.open_cloud_window)

    def available(self) -> bool:
        if self.job is None:
            return True
        self.status.set("Дождитесь завершения операции.")
        return False

    def run(self, operation, done) -> None:
        if not self.available():
            return
        generation = self.generation
        self.status.set("Выполняется операция…")
        future = self.pool.submit(operation)
        self.job = future
        self.set_wait_cursor(True)
        if self.cloud_window:
            self.cloud_window.sync_actions()
        self.root.after(30, self.poll, future, generation, done)

    def poll(self, future: Future, generation: int, done) -> None:
        if not future.done():
            self.root.after(30, self.poll, future, generation, done)
            return
        self.job = None
        self.set_wait_cursor(False)
        parent = self.cloud_window or self.root
        if self.editor and self.editor.winfo_exists():
            parent = self.editor
        self.cloud_cancel = None
        if self.cloud_window:
            self.cloud_window.sync_actions()
        if generation != self.generation:
            return
        self.status.set("")
        try:
            result = future.result()
        except HexageError as error:
            dialogs.show_message("Hexage", str(error), parent=parent)
        except Exception:
            dialogs.show_message(
                "Hexage", "Не удалось выполнить операцию.", parent=parent
            )
        else:
            done(result)

    def set_wait_cursor(self, waiting: bool) -> None:
        widgets: list[tk.Misc] = [self.root]
        if self.cloud_window:
            widgets.append(self.cloud_window)
        if self.editor and self.editor.winfo_exists():
            widgets.extend((self.editor, self.editor.name, self.editor.text))
        for widget in widgets:
            # Text fields have their own cursor and do not inherit the window's.
            default = widget.configure("cursor")[-2]
            widget.configure(cursor="watch" if waiting else default)

    def activate(self, session: Session) -> None:
        self.session = session
        self.activity()
        self.render()
        if self.cloud_window:
            self.cloud_window.sync_actions()
        if not session.durable:
            self.status.set("Файл записан, но синхронизация каталога не подтверждена.")

    def password(
        self, prompt: str, parent: tk.Tk | tk.Toplevel | None = None
    ) -> str | None:
        return dialogs.ask_password(prompt, parent=parent or self.root)

    def new_password(self) -> str | None:
        password = self.password("Новый пароль")
        if password is None:
            return None
        confirmation = self.password("Повторите новый пароль")
        if confirmation is None:
            return None
        if not password or password != confirmation:
            dialogs.show_message(
                "Hexage", "Пароли пусты или не совпадают.", parent=self.root
            )
            return None
        return password

    def create(self) -> None:
        if self.available() and (password := self.new_password()) is not None:
            self.run(lambda: initialize(self.store, password), self.activate)

    def unlock(self) -> None:
        if (
            self.available()
            and (password := self.password("Пароль хранилища")) is not None
        ):
            self.run(lambda: unlock(self.store, password), self.activate)

    def discard_editor(self) -> None:
        if self.editor and self.editor.winfo_exists():
            self.editor.destroy()
        self.editor = None

    def dirty(self) -> bool:
        return bool(self.editor and self.editor.winfo_exists() and self.editor.dirty())

    def confirm_discard(self) -> bool:
        return not self.dirty() or dialogs.ask_yes_no(
            "Несохранённые изменения",
            "Отбросить правки?",
            parent=self.root,
        )

    def lock(self, force: bool = False) -> None:
        if force or self.confirm_discard():
            if self.cloud_cancel is not None:
                self.cloud_cancel.set()
            self.generation += 1
            self.set_wait_cursor(False)
            self.session = None
            self.visible_notes = ()
            self.filter_text.set("")
            self.discard_editor()
            self.destroy_cloud_window()
            self.status.set("Хранилище заблокировано.")
            self.render()

    def close(self) -> None:
        if has_modal_child(self.root):
            return
        if self.confirm_discard():
            if self.cloud_cancel is not None:
                self.cloud_cancel.set()
            self.generation += 1
            self.pool.shutdown(wait=False, cancel_futures=True)
            self.root.destroy()

    def edit(self, note: Note | None) -> None:
        if not self.available() or self.session is None:
            return
        if self.editor and self.editor.winfo_exists():
            self.editor.lift()
            return
        self.editor = Editor(self.root, note, self.save_note)
        self.editor.show()

    def open_selected(self) -> None:
        if self.session and (selected := self.list.curselection()):
            self.edit(self.visible_notes[selected[0]])

    def save_note(self, editor: Editor, note: Note) -> None:
        session = self.session
        if not session or not self.available():
            return
        current = session.opened.vault.notes
        notes = tuple(note if item.id == note.id else item for item in current)
        if editor.note is None:
            notes = (*notes, note)
        editor.name.configure(state="readonly")
        editor.text.configure(state="disabled")
        self.run(lambda: save(self.store, session, notes), self.activate_saved)
        self.root.after(40, self.resume_editor, editor)

    def activate_saved(self, session: Session) -> None:
        self.discard_editor()
        self.activate(session)

    def resume_editor(self, editor: Editor) -> None:
        if not editor.winfo_exists():
            return
        if self.job is not None:
            self.root.after(40, self.resume_editor, editor)
        else:
            editor.set_mode(True)

    def delete(self) -> None:
        session = self.session
        if not session or not self.ready_for_replacement():
            return
        selected = {self.visible_notes[i].id for i in self.list.curselection()}
        if (
            selected
            and dialogs.ask_yes_no(
                "Удаление",
                f"Удалить выбранные заметки ({len(selected)})?",
                parent=self.root,
            )
            and self.session is session
        ):
            notes = tuple(n for n in session.opened.vault.notes if n.id not in selected)
            self.run(lambda: save(self.store, session, notes), self.activate_saved)

    def ready_for_replacement(self) -> bool:
        if not self.available():
            return False
        if self.dirty():
            self.status.set("Сначала сохраните правки или закройте редактор.")
            return False
        return True

    def change_password(self) -> None:
        session = self.session
        if session is None or not self.ready_for_replacement():
            return
        if not dialogs.ask_yes_no(
            "Смена пароля",
            "Старые снимки открываются прежним паролем. "
            "Для обновления облачной копии нужен ручной экспорт.",
            parent=self.root,
        ):
            return
        current = self.password("Текущий пароль")
        new = self.new_password() if current is not None else None
        if new is not None and self.session is session and self.ready_for_replacement():
            self.run(
                lambda: change_password(self.store, session, current, new),
                self.activate,
            )

    def restore_file(self) -> None:
        if not self.ready_for_replacement():
            return
        session, generation = self.session, self.generation
        name = filedialog.askopenfilename(filetypes=FILES, parent=self.root)
        if not name or generation != self.generation:
            return
        password = self.password("Пароль выбранного снимка")
        if password is not None and generation == self.generation:
            self.run(
                lambda: plan_restore(read_file(Path(name)), password, session),
                lambda plan: self.confirm_restore(plan, session),
            )

    def confirm_restore(
        self,
        plan: RestorePlan,
        session: Session | None,
        parent: tk.Tk | tk.Toplevel | None = None,
    ) -> None:
        title = "Восстановление"
        parent = parent or self.root
        if not plan.can_apply():
            dialogs.show_message(title, plan.relation.value, parent=parent)
            return
        generation = self.generation
        confirmed = dialogs.ask_yes_no(
            title,
            restore_summary(plan, session),
            parent=parent,
        )
        if (
            confirmed
            and generation == self.generation
            and self.session is session
            and self.ready_for_replacement()
        ):
            self.discard_editor()
            self.run(lambda: plan.apply(self.store), self.activate_saved)

    def export(self) -> None:
        session = self.session
        if not session or not self.available():
            return
        name = self.export_path()
        if name and self.session is session:
            self.run(
                lambda: self.store.export(Path(name), session.digest), self.exported
            )

    def export_path(self) -> str:
        return filedialog.asksaveasfilename(
            filetypes=FILES,
            defaultextension=".hexage",
            parent=self.root,
            confirmoverwrite=False,
        )

    def exported(self, durable: bool) -> None:
        self.status.set(
            "Снимок сохранён." if durable else "Снимок записан без подтверждения fsync."
        )

    def open_cloud_window(self) -> None:
        if self.cloud_window:
            self.cloud_window.deiconify()
            self.cloud_window.lift()
            return
        if self.clouds and self.available():
            self.cloud_window = CloudWindow(self)
            self.cloud_window.show()

    def close_cloud_window(self) -> None:
        if self.cloud_window and has_modal_child(self.cloud_window):
            return
        self.cancel_cloud()
        self.destroy_cloud_window()

    def destroy_cloud_window(self) -> None:
        if self.cloud_window:
            self.cloud_window.destroy()
            self.cloud_window = None

    def cancel_cloud(self) -> None:
        if self.cloud_cancel is None or self.cloud_cancel.is_set():
            return
        self.cloud_cancel.set()
        self.generation += 1
        self.set_wait_cursor(False)
        self.status.set("Операция отменена. Облачное хранилище могло уже измениться.")
        if self.cloud_window:
            self.cloud_window.clear_snapshots()

    def run_cloud(self, operation, done) -> None:
        if self.cloud_window and self.available():
            cancel = self.cloud_cancel = Event()
            self.run(lambda: operation(cancel), done)

    def refresh_cloud(self) -> None:
        if (window := self.cloud_window) and self.available():
            cloud = window.current_cloud()
            window.clear_snapshots()
            self.run_cloud(
                lambda cancel: cloud.call(lambda adapter: adapter.list(), cancel),
                window.show_snapshots,
            )

    def restore_cloud(self) -> None:
        window = self.cloud_window
        if not window or not self.ready_for_replacement():
            return
        session = self.session
        snapshot = window.selected_snapshot()
        if snapshot is None:
            return
        cloud = window.current_cloud()
        self.run_cloud(
            lambda cancel: cloud.call(
                lambda adapter: adapter.download(snapshot), cancel
            ),
            lambda blob: self.open_cloud_snapshot(window, blob, session),
        )

    def open_cloud_snapshot(
        self, window: CloudWindow, blob: bytes, session: Session | None
    ) -> None:
        generation = self.generation
        password = self.password("Пароль выбранного снимка", parent=window)
        if (
            password is not None
            and self.cloud_window is window
            and generation == self.generation
            and self.session is session
            and self.ready_for_replacement()
        ):
            self.run_cloud(
                lambda _: plan_restore(blob, password, session),
                lambda plan: self.confirm_restore(plan, session, parent=window),
            )

    def export_cloud(self) -> None:
        window, session = self.cloud_window, self.session
        if not window or not session or not self.available():
            return
        targets = choose(
            window,
            "Куда экспортировать снимок",
            list(self.clouds.items()),
            multiple=True,
        )
        if targets and self.cloud_window is window and self.session is session:
            self.run_cloud(
                lambda cancel: export_to(
                    tuple(targets), self.store.snapshot(session.digest), cancel
                ),
                lambda results: self.cloud_exported(window, targets, results),
            )

    def cloud_exported(
        self, window: CloudWindow, targets: list[Cloud], results: dict[str, str]
    ) -> None:
        current = window.current_cloud()
        if current in targets:
            window.clear_snapshots()
        dialogs.show_message(
            "Экспорт в облако",
            "\n".join(f"{target} — {status}" for target, status in results.items()),
            parent=window,
        )
        if (
            self.cloud_window is window
            and results.get(current.provider.name) == EXPORT_OK
        ):
            self.refresh_cloud()

    def delete_cloud_snapshot(self) -> None:
        window = self.cloud_window
        if (
            not window
            or not self.available()
            or (snapshot := window.selected_snapshot()) is None
        ):
            return
        cloud = window.current_cloud()
        generation = self.generation
        confirmed = dialogs.ask_yes_no(
            "Удалить облачный снимок?",
            f"{cloud.provider.name}\nСохранён в облаке: {snapshot.label()}\n\n"
            "Выбранная копия будет удалена окончательно.",
            parent=window,
        )
        if confirmed and self.cloud_window is window and generation == self.generation:
            self.run_cloud(
                lambda cancel: cloud.call(
                    lambda adapter: adapter.delete(snapshot), cancel
                ),
                lambda _: self.cloud_snapshot_deleted(window, snapshot),
            )

    def cloud_snapshot_deleted(self, window: CloudWindow, snapshot: Snapshot) -> None:
        window.show_snapshots([item for item in window.snapshots if item != snapshot])
        self.status.set("Облачный снимок удалён.")

    def disconnect_cloud(self) -> None:
        if (window := self.cloud_window) and self.available():
            cloud = window.current_cloud()
            self.run_cloud(
                lambda _: cloud.credentials.disconnect(cloud.provider, strict=True),
                lambda _: self.cloud_disconnected(window),
            )

    def cloud_disconnected(self, window: CloudWindow) -> None:
        window.clear_snapshots()
        self.status.set("Аккаунт отключён.")


def restore_summary(plan: RestorePlan, session: Session | None) -> str:
    lines = [plan.relation.value, f"Снимок (UTC)  {plan.opened.vault.changed}"]
    if session:
        lines.extend(
            [
                f"Активная ревизия (UTC)  {session.opened.vault.changed}",
                "Выбранный снимок целиком заменит активное хранилище.",
                "Перед заменой будет записана зашифрованная резервная копия.",
            ]
        )
    lines.append("После восстановления действует пароль выбранного снимка.")
    return "\n".join(lines)


def _enable_system_dpi() -> None:
    if sys.platform == "win32":
        from ctypes import windll

        # The EXE declares this in its manifest; a direct Python launch needs
        # it before Tk creates a window. Tk 8.6 uses one scale for the session.
        windll.user32.SetProcessDPIAware()


def _configure_fonts(root: tk.Tk) -> None:
    fonts.apply(root)
    if message := fonts.legacy_fonts_message(root):
        print(message, file=sys.stderr)


def main() -> None:
    _enable_system_dpi()
    root = tk.Tk()
    _configure_fonts(root)
    root.title("Hexage")
    assets = files(__package__).joinpath("assets")
    icons = [
        tk.PhotoImage(
            master=root, data=assets.joinpath(f"hexage-{size}.png").read_bytes()
        )
        for size in (32, 48, 256)
    ]
    root.iconphoto(True, *icons)
    path = config_path()
    warning = None
    try:
        ensure_config(path)
        config = load_oauth_config(path)
    except HexageError as error:
        warning = f"{error}\n\n{path}\n\nОблачный обмен отключён до перезапуска."
        config = OAuthConfig()
    app = App(root, Store(default_path()), config)
    # A transient dialog cannot appear until the window manager maps its owner.
    root.wait_visibility()
    if warning:
        dialogs.show_message(
            "Настройки Hexage",
            warning,
            parent=root,
        )
    if not app.needs_setup():
        root.after_idle(app.unlock)
    root.mainloop()
