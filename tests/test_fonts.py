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

from hexage.fonts import PREFERRED_FAMILIES, choose_family


def test_no_known_family_returns_none():
    assert choose_family([]) is None
    assert choose_family(["Comic Sans MS"]) is None


def test_single_known_family_is_selected():
    assert choose_family(["Arial"]) == "Arial"


def test_preference_order_wins_over_input_order():
    available = ["Nimbus Sans", "Arial", "DejaVu Sans"]
    assert choose_family(available) == "DejaVu Sans"


def test_match_is_case_insensitive_and_keeps_platform_name():
    assert choose_family(["DEJAVU SANS"]) == "DEJAVU SANS"


def test_preferred_families_have_no_duplicates():
    folded = [name.casefold() for name in PREFERRED_FAMILIES]
    assert len(folded) == len(set(folded))
