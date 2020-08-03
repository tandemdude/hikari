# -*- coding: utf-8 -*-
# Copyright © Nekoka.tt 2019-2020
#
# This file is part of Hikari.
#
# Hikari is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hikari is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Hikari. If not, see <https://www.gnu.org/licenses/>.

from hikari.models import audit_logs


def test_AuditLogChangeKey_str_operator():
    change_key = audit_logs.AuditLogChangeKey("owner_id")
    assert str(change_key) == "OWNER_ID"


def test_AuditLogEventType_str_operator():
    event_type = audit_logs.AuditLogEventType(80)
    assert str(event_type) == "INTEGRATION_CREATE"


def test_AuditLog_itter():
    entry = audit_logs.AuditLogEntry()
    entry.id = 1
    entry2 = audit_logs.AuditLogEntry()
    entry2.id = 2
    entry3 = audit_logs.AuditLogEntry()
    entry3.id = 3
    audit_log = audit_logs.AuditLog()
    audit_log.entries = {1: entry, 2: entry2, 3: entry3}

    assert len(audit_log) == 3
    assert [*audit_log] == [entry, entry2, entry3]