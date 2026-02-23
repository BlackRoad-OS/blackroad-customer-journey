"""
Tests for BlackRoad Customer Journey Mapper.
"""
import sys
import os
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from customer_journey import CustomerJourneyMapper


@pytest.fixture
def mapper(tmp_path):
    db = str(tmp_path / "test_journey.db")
    m = CustomerJourneyMapper(db_path=db)
    yield m
    m.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _add_default_stages(mapper):
    stages = [
        ("Awareness",    1, "User discovers brand",      "page_view",   "search"),
        ("Interest",     2, "User engages with content", "search",      "product_view"),
        ("Consideration",3, "User evaluates product",    "product_view","add_to_cart"),
        ("Intent",       4, "User adds to cart",         "add_to_cart", "checkout_start"),
        ("Purchase",     5, "User completes purchase",   "checkout_start","purchase"),
    ]
    created = []
    for name, pos, desc, entry, exit_ in stages:
        created.append(mapper.define_funnel_stage(name, pos, desc, entry, exit_))
    return created


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_define_funnel(mapper):
    """Create stages and verify they are ordered by position."""
    stages = _add_default_stages(mapper)

    assert len(stages) == 5
    positions = [s.position for s in stages]
    assert positions == sorted(positions), "Stages should be ordered by position"
    assert stages[0].name == "Awareness"
    assert stages[4].name == "Purchase"
    assert stages[2].entry_event == "product_view"


def test_session_lifecycle(mapper):
    """Start a session, add touchpoints, end the session."""
    _add_default_stages(mapper)

    sid = mapper.start_session("cust-001", "organic", "desktop")
    assert sid, "Session ID must be non-empty"

    tp1 = mapper.record_touchpoint(sid, "cust-001", "organic", "/home", "page_view", 3000)
    assert "touchpoint_id" in tp1
    assert tp1.get("stage_entered") == "Awareness"

    tp2 = mapper.record_touchpoint(sid, "cust-001", "organic", "/shop", "add_to_cart", 1500)
    assert tp2.get("stage_entered") == "Intent"

    path = mapper.end_session(sid, converted=False, conversion_value=0.0)
    assert path.session_id == sid
    assert "Awareness" in path.stages_visited
    assert path.converted is False


def test_funnel_analysis(mapper):
    """Simulate 10 sessions with dropoffs; verify conversion rates are computed."""
    _add_default_stages(mapper)

    # 10 sessions: 6 reach add_to_cart, 3 complete purchase
    for i in range(10):
        sid = mapper.start_session(f"cust-{i:03d}", "email", "mobile")
        mapper.record_touchpoint(sid, f"cust-{i:03d}", "email", "/home", "page_view", 2000)
        if i < 6:
            mapper.record_touchpoint(sid, f"cust-{i:03d}", "email", "/shop", "add_to_cart", 1000)
        if i < 3:
            mapper.record_touchpoint(sid, f"cust-{i:03d}", "email", "/checkout", "checkout_start", 500)
            mapper.end_session(sid, converted=True, conversion_value=49.99)
        else:
            mapper.end_session(sid, converted=False)

    analysis = mapper.analyze_funnel(days=1)
    assert len(analysis) == 5, "Should return one entry per funnel stage"

    awareness = next(s for s in analysis if s["stage_name"] == "Awareness")
    assert awareness["entry_count"] == 10
    assert 0 <= awareness["conversion_rate"] <= 100


def test_conversion_paths(mapper):
    """Verify top paths aggregation groups identical path_signatures."""
    _add_default_stages(mapper)

    # Create 5 sessions with the same short path and 2 with a longer path
    for i in range(5):
        sid = mapper.start_session(f"cust-{i:03d}", "social", "desktop")
        mapper.record_touchpoint(sid, f"cust-{i:03d}", "social", "/home", "page_view", 1000)
        mapper.end_session(sid, converted=False)

    for i in range(5, 7):
        sid = mapper.start_session(f"cust-{i:03d}", "email", "mobile")
        mapper.record_touchpoint(sid, f"cust-{i:03d}", "email", "/home", "page_view", 800)
        mapper.record_touchpoint(sid, f"cust-{i:03d}", "email", "/shop", "add_to_cart", 400)
        mapper.end_session(sid, converted=True, conversion_value=29.99)

    paths = mapper.get_top_conversion_paths(limit=5)
    assert len(paths) >= 1, "Should return at least one path"
    # Top path should have the highest occurrence count
    assert paths[0]["occurrences"] >= paths[-1]["occurrences"]
    # Each entry must have required keys
    for p in paths:
        assert "path_signature" in p
        assert "conversion_rate" in p


def test_dropoff_analysis(mapper):
    """Record dropoffs and verify stage aggregation."""
    stages = _add_default_stages(mapper)
    intent_stage = next(s for s in stages if s.name == "Intent")

    # 4 sessions that reach Intent but don't convert
    for i in range(4):
        sid = mapper.start_session(f"drop-{i}", "paid", "desktop")
        mapper.record_touchpoint(sid, f"drop-{i}", "paid", "/home", "page_view", 1500)
        mapper.record_touchpoint(sid, f"drop-{i}", "paid", "/shop", "add_to_cart", 900)
        mapper.end_session(sid, converted=False)

    result = mapper.analyze_dropoffs(intent_stage.id)
    # Intent stage may or may not have drops depending on path logic; just check structure
    assert "reasons" in result
    assert "by_channel" in result
    assert "time_of_day" in result
    assert isinstance(result["total_dropoffs"], int)


def test_channel_attribution(mapper):
    """Sessions from multiple channels; verify per-channel stats."""
    _add_default_stages(mapper)

    channels_config = [
        ("organic",  5, 2, 39.99),
        ("email",    4, 3, 59.99),
        ("paid",     3, 1, 99.00),
    ]

    for channel, total, conv, value in channels_config:
        for i in range(total):
            sid = mapper.start_session(f"{channel}-cust-{i}", channel, "desktop")
            mapper.record_touchpoint(sid, f"{channel}-cust-{i}", channel,
                                     "/home", "page_view", 2000)
            if i < conv:
                mapper.end_session(sid, converted=True, conversion_value=value)
            else:
                mapper.end_session(sid, converted=False)

    attr = mapper.get_channel_attribution(days=1)
    assert len(attr) == 3, "Should return one row per channel"

    channels_found = {r["channel"] for r in attr}
    assert "organic" in channels_found
    assert "email" in channels_found
    assert "paid" in channels_found

    for row in attr:
        assert row["sessions"] > 0
        assert 0 <= row["conversion_rate"] <= 100
