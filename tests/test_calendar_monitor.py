from datetime import datetime, timezone

from life_cli import calendar_monitor as cm
from life_cli.core.models import CalendarEvent


def _ev(i, summary="Mtg", start=None, end=None, **kw):
    return CalendarEvent(
        id=i, summary=summary,
        start=start or datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        end=end or datetime(2026, 1, 1, 11, tzinfo=timezone.utc), **kw)


class _Cal:
    def __init__(self, events, seen):
        self._events, self._seen = events, seen

    def list_events(self, time_min=None, time_max=None, max_results=50):
        self._seen.update(time_min=time_min, time_max=time_max, max_results=max_results)
        return self._events


class _Prov:
    def __init__(self, cal):
        self._cal = cal

    def calendar(self):
        return self._cal


# ---- snapshot ----

def test_snapshot_queries_90_day_window(monkeypatch):
    seen = {}
    monkeypatch.setattr(cm, "get_provider",
                        lambda p, a: _Prov(_Cal([_ev("e1")], seen)))
    out = cm.snapshot("google", "why")
    assert out[0].id == "e1"
    delta = datetime.fromisoformat(seen["time_max"]) - datetime.fromisoformat(seen["time_min"])
    assert delta.days == 90
    assert seen["max_results"] == 2500


def test_snapshot_no_calendar_raises(monkeypatch):
    monkeypatch.setattr(cm, "get_provider", lambda p, a: _Prov(None))
    try:
        cm.snapshot("google")
        assert False
    except ValueError as e:
        assert "calendar" in str(e)


# ---- diff ----

def test_diff_added_removed():
    d = cm.diff([_ev("a"), _ev("b")], [_ev("b"), _ev("c")])
    assert [e.id for e in d["added"]] == ["c"]
    assert [e.id for e in d["removed"]] == ["a"]
    assert d["changed"] == []


def test_diff_changed_reports_field_deltas():
    old = [_ev("a", summary="Old", location="Room1")]
    new = [_ev("a", summary="New", location="Room1")]
    d = cm.diff(old, new)
    assert d["added"] == [] and d["removed"] == []
    ch = d["changed"][0]
    assert ch["id"] == "a"
    assert ch["fields"] == {"summary": {"old": "Old", "new": "New"}}


def test_diff_time_change_detected():
    old = [_ev("a", start=datetime(2026, 1, 1, 10, tzinfo=timezone.utc))]
    new = [_ev("a", start=datetime(2026, 1, 1, 14, tzinfo=timezone.utc))]
    ch = cm.diff(old, new)["changed"][0]
    assert "start" in ch["fields"]


def test_diff_identical_no_change():
    same = [_ev("a"), _ev("b")]
    assert cm.diff(same, list(same)) == {"added": [], "removed": [], "changed": []}


# ---- persistence ----

def test_save_load_roundtrip(tmp_path):
    p = str(tmp_path / "snap.json")
    events = [_ev("a", attendees=["x@x.com"], description="d")]
    cm.save_snapshot(p, events)
    loaded = cm.load_snapshot(p)
    assert loaded[0].id == "a"
    assert loaded[0].attendees == ["x@x.com"]
    assert loaded[0].start == events[0].start
    assert cm.diff(events, loaded) == {"added": [], "removed": [], "changed": []}


# ---- monitor ----

def test_monitor_first_run_all_added(monkeypatch, tmp_path):
    p = str(tmp_path / "snap.json")
    monkeypatch.setattr(cm, "get_provider",
                        lambda pr, a: _Prov(_Cal([_ev("e1")], {})))
    d = cm.monitor("google", None, p)
    assert [e.id for e in d["added"]] == ["e1"]
    assert cm.load_snapshot(p)[0].id == "e1"


def test_monitor_second_run_diffs_prev(monkeypatch, tmp_path):
    p = str(tmp_path / "snap.json")
    cm.save_snapshot(p, [_ev("e1", summary="Old")])
    monkeypatch.setattr(cm, "get_provider",
                        lambda pr, a: _Prov(_Cal([_ev("e1", summary="New"), _ev("e2")], {})))
    d = cm.monitor("google", "why", p)
    assert [e.id for e in d["added"]] == ["e2"]
    assert d["changed"][0]["fields"]["summary"] == {"old": "Old", "new": "New"}
    assert {e.id for e in cm.load_snapshot(p)} == {"e1", "e2"}
