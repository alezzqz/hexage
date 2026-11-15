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
from functools import lru_cache
from importlib.resources import files
from tkinter import ttk

# Use the original PNG at each size so icons stay sharp without a raster dependency.
ICON_SIZES = (24, 32, 48)


@lru_cache(maxsize=64)
def _icon_data(icon: str, size: int) -> bytes:
    return (
        files(__package__)
        .joinpath("assets", "icons8", str(size), f"{icon}.png")
        .read_bytes()
    )


class IconButton(ttk.Button):
    def __init__(
        self, parent: tk.Misc, icon: str, label: str, command: Callable[[], object]
    ) -> None:
        super().__init__(parent, text=label, command=command, takefocus=True)
        style = ttk.Style(self)
        target = self.winfo_fpixels("18p")
        size = min(ICON_SIZES, key=lambda pixels: abs(pixels - target))
        self._icon = tk.PhotoImage(master=self, data=_icon_data(icon, size))
        style.configure("Icon.TButton", padding=(4, 4), width=0)
        self.configure(
            style="Icon.TButton",
            compound="image",
            image=self._icon,
        )
        self._tip: tk.Toplevel | None = None
        self._tip_job: str | None = None
        # Returning focus after a modal dialog is not keyboard traversal.
        for event in ("<Enter>", "<<TraverseIn>>"):
            self.bind(event, self._schedule_tip, add="+")
        for event in (
            "<Leave>",
            "<FocusOut>",
            "<ButtonPress>",
            "<KeyPress>",
            "<Unmap>",
            "<Destroy>",
        ):
            self.bind(event, self._hide_tip, add="+")

    def _schedule_tip(self, event: tk.Event) -> None:
        self._hide_tip(event)
        from_pointer = event.type == tk.EventType.Enter
        self._tip_job = self.after(450, self._show_tip, from_pointer)

    def _show_tip(self, from_pointer: bool) -> None:
        self._tip_job = None
        if not self.winfo_ismapped():
            return
        grab = str(self.tk.call("grab", "current", self))
        if grab not in ("", str(self.winfo_toplevel())):
            return
        if from_pointer:
            x, y = self.winfo_pointerxy()
            hovered = self.tk.call("winfo", "containing", "-displayof", self, x, y)
            if str(hovered) != str(self):
                return
        elif self.focus_get() is not self:
            return
        tip = self._tip = tk.Toplevel(self)
        tip.withdraw()
        tip.overrideredirect(True)
        ttk.Label(tip, text=self.cget("text"), padding=(8, 4), relief="solid").pack()
        tip.update_idletasks()
        x, y = self.winfo_rootx(), self.winfo_rooty()
        right = self.winfo_vrootx() + self.winfo_vrootwidth()
        bottom = self.winfo_vrooty() + self.winfo_vrootheight()
        x = min(x, right - tip.winfo_reqwidth())
        below = y + self.winfo_height() + 5
        if below + tip.winfo_reqheight() > bottom:
            below = y - tip.winfo_reqheight() - 5
        tip.geometry(f"+{x}+{below}")
        tip.deiconify()
        tip.lift()

    def _hide_tip(self, _event: tk.Event) -> None:
        if self._tip_job is not None:
            self.after_cancel(self._tip_job)
            self._tip_job = None
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


def pack_icon(
    parent: tk.Misc, icon: str, label: str, command: Callable[[], object]
) -> None:
    IconButton(parent, icon, label, command).pack(side="left", padx=(0, 4))
