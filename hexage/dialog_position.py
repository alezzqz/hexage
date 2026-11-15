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


def show_modal(
    dialog: tk.Toplevel, focus: tk.Widget, *, size: tuple[int, int] | None = None
) -> bool:
    parent = dialog.master
    dialog.transient(parent)
    previous_grab = dialog.grab_current()
    previous_focus = parent.focus_lastfor()
    _show_centered(dialog, parent, size=size)
    try:
        if not dialog.winfo_viewable():
            dialog.wait_visibility()
    except tk.TclError:
        if dialog.winfo_exists():
            raise
        return False
    dialog.grab_set()
    dialog.bind(
        "<Destroy>",
        lambda event: _restore_input(event, dialog, previous_grab, previous_focus),
        add="+",
    )
    focus.focus_set()
    return True


def _restore_input(
    event: tk.Event,
    dialog: tk.Toplevel,
    previous_grab: tk.Misc | None,
    previous_focus: tk.Misc | None,
) -> None:
    # Toplevel bindings also see descendant destruction. A newer dialog may
    # already own the grab, so do not replace it when closing this one.
    if event.widget is not dialog or dialog.grab_current() not in (None, dialog):
        return
    if previous_grab is not None and previous_grab.winfo_exists():
        previous_grab.grab_set()
    if previous_focus is not None and previous_focus.winfo_exists():
        previous_focus.focus_set()


def has_modal_child(window: tk.Tk | tk.Toplevel) -> bool:
    # Tk can give the grab to widgets it creates internally, such as a dropdown.
    return str(window.tk.call("grab", "current", window)) not in ("", str(window))


def _show_centered(
    dialog: tk.Toplevel, anchor: tk.Misc, *, size: tuple[int, int] | None = None
) -> None:
    dialog.update_idletasks()
    width, height = size or (dialog.winfo_reqwidth(), dialog.winfo_reqheight())
    # Geometry uses window-manager coordinates, including the title bar offset.
    x = anchor.winfo_x() + (anchor.winfo_width() - width) // 2
    y = anchor.winfo_y() + (anchor.winfo_height() - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    dialog.deiconify()
