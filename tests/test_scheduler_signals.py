from backend.scheduler import _parse_signals, _strip_signals_block


def test_parse_signals_from_output():
    output = """Here is my analysis of the market.

Key finding: new integration opportunity with Zapier.

SIGNALS:
- social:linkedin :: New Zapier integration announcement — strong LinkedIn angle for SaaS audience
- email:customers :: Announce Zapier integration to existing customers
END_SIGNALS

STATUS:OK"""
    signals = _parse_signals(output)
    assert len(signals) == 2
    assert signals[0] == ("social:linkedin", "New Zapier integration announcement — strong LinkedIn angle for SaaS audience")
    assert signals[1] == ("email:customers", "Announce Zapier integration to existing customers")

    stripped = _strip_signals_block(output)
    assert "SIGNALS:" not in stripped
    assert "END_SIGNALS" not in stripped
    assert "STATUS:OK" in stripped
    assert "Key finding" in stripped


def test_parse_signals_empty():
    from backend.scheduler import _parse_signals
    assert _parse_signals("No signals here.\nSTATUS:OK") == []


def test_parse_signals_malformed_line_skipped():
    output = "SIGNALS:\n- bad line no delimiter\n- social:linkedin :: Good line\nEND_SIGNALS"
    signals = _parse_signals(output)
    assert len(signals) == 1
    assert signals[0][0] == "social:linkedin"


def test_strip_signals_block_preserves_surrounding_content():
    output = "Before.\n\nSIGNALS:\n- social:linkedin :: Test\nEND_SIGNALS\n\nAfter."
    stripped = _strip_signals_block(output)
    assert "Before." in stripped
    assert "After." in stripped
    assert "SIGNALS:" not in stripped
    assert "social:linkedin" not in stripped


def test_parse_signals_no_block():
    output = "Just a plain output.\nSTATUS:OK"
    assert _parse_signals(output) == []
    stripped = _strip_signals_block(output)
    assert stripped == "Just a plain output.\nSTATUS:OK"
