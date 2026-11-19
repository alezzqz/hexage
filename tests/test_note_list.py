"""Headless checks for visible-note selection and deletion boundaries."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from hexage.model import Note
from hexage.ui import App


@pytest.fixture
def app() -> App:
    app = App.__new__(App)
    notes = (
        Note("1" * 32, "Яблоко", ""),
        Note("2" * 32, "енот", ""),
        Note("3" * 32, "Бета", ""),
        Note("4" * 32, "Ёж", ""),
        Note("5" * 32, "альфа БЕТА", ""),
        Note("6" * 32, "Бета", "дубликат названия"),
    )
    app.session = SimpleNamespace(
        opened=SimpleNamespace(vault=SimpleNamespace(notes=notes))
    )
    app.visible_notes = ()
    app.list = Mock()
    app.list.curselection.return_value = ()
    app.filter_text = Mock()
    app.filter_text.get.return_value = ""
    return app


@pytest.mark.parametrize(
    ("query", "ids"),
    [("", "536421"), ("бЕт", "536"), ("ЛОК", "1"), ("нет совпадений", "")],
)
def test_filter_and_sort(app: App, query: str, ids: str) -> None:
    original = app.session.opened.vault.notes
    app.filter_text.get.return_value = query
    app.refresh_notes()
    assert tuple(n.id for n in app.visible_notes) == tuple(i * 32 for i in ids)
    assert app.session.opened.vault.notes is original


def test_selection_tracks_note_when_filter_changes(app: App) -> None:
    app.refresh_notes()
    app.list.curselection.return_value = (2,)
    app.filter_text.get.return_value = "БЕТ"
    app.refresh_notes()
    app.list.selection_set.assert_called_once_with(2)
    app.edit = Mock()
    app.open_selected()
    app.edit.assert_called_once_with(app.session.opened.vault.notes[5])


def test_delete_only_selected_visible_note(app: App) -> None:
    app.filter_text.get.return_value = "БЕТ"
    app.refresh_notes()
    app.list.curselection.return_value = (2,)
    app.ready_for_replacement = Mock(return_value=True)
    app.root, app.store = Mock(), Mock()
    app.run = Mock(side_effect=lambda operation, done: operation())
    original = app.session.opened.vault.notes
    with patch("hexage.ui.dialogs.ask_yes_no", return_value=True):
        with patch("hexage.ui.save") as save:
            app.delete()
    save.assert_called_once_with(app.store, app.session, original[:5])
