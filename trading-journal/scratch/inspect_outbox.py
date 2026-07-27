#!/usr/bin/env python3
import sqlite3

con = sqlite3.connect("_journal_data/outbox.db")
con.row_factory = sqlite3.Row

print("STATUS")
for row in con.execute("select status, count(*) count from outbox_events group by status order by status"):
    print(dict(row))

print("LATEST NON-SENT")
for row in con.execute(
    """
    select event_id, status, attempts, last_error,
           datetime(created_at, 'unixepoch') created_at,
           datetime(updated_at, 'unixepoch') updated_at
    from outbox_events
    where status != 'sent'
    order by updated_at desc
    limit 20
    """
):
    print(dict(row))

print("TYPE STATUS")
for row in con.execute(
    """
    select
      case
        when event_id like 'trade-%' then 'trade'
        when event_id like 'snapshot-%' then 'snapshot'
        else 'other'
      end kind,
      status,
      count(*) count
    from outbox_events
    group by kind, status
    order by kind, status
    """
):
    print(dict(row))

print("LATEST TRADE EVENTS")
for row in con.execute(
    """
    select event_id, status, attempts, last_error,
           datetime(created_at, 'unixepoch') created_at,
           datetime(updated_at, 'unixepoch') updated_at,
           substr(payload_json, 1, 220) payload_head
    from outbox_events
    where event_id like 'trade-%'
    order by created_at desc
    limit 20
    """
):
    print(dict(row))
