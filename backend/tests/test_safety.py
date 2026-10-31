"""The dry-run / no-send guard is a backend rule, not a UI control."""

from __future__ import annotations

import pytest

from app.safety import (
    SEND_FUNCTIONS,
    Channel,
    SendNotPermittedError,
    describe_safety,
    evaluate_outreach,
    get_sender,
    is_dry_run,
    send_email,
    send_sms,
)


def test_dry_run_is_on_by_default():
    assert is_dry_run() is True


def test_every_registered_sender_raises():
    for channel, sender in SEND_FUNCTIONS.items():
        with pytest.raises(SendNotPermittedError) as excinfo:
            sender()
        assert channel.value in str(excinfo.value)


@pytest.mark.parametrize(
    "sender",
    [send_email, send_sms, *SEND_FUNCTIONS.values()],
)
def test_send_functions_never_return(sender):
    """A send function must raise rather than complete successfully."""
    with pytest.raises(SendNotPermittedError):
        sender("someone@example.com", "hello")


def test_get_sender_returns_guarded_callable():
    sender = get_sender(Channel.EMAIL)
    with pytest.raises(SendNotPermittedError):
        sender(to="a@b.com", subject="hi", body="hello")


def test_get_sender_rejects_unknown_channel():
    with pytest.raises(ValueError):
        get_sender("carrier_pigeon")


def test_evaluate_outreach_blocked_without_approval():
    decision = evaluate_outreach("email", approved=False)
    assert decision.result == "BLOCKED"
    assert decision.would_send is False
    assert "approval" in decision.reason.lower()


def test_evaluate_outreach_blocked_in_dry_run_even_with_approval():
    decision = evaluate_outreach("linkedin", approved=True)
    assert decision.result == "BLOCKED"
    assert decision.would_send is False
    assert decision.dry_run is True


def test_evaluate_outreach_rejects_unknown_channel():
    with pytest.raises(ValueError):
        evaluate_outreach("fax")


def test_describe_safety_reports_zero_sends():
    payload = describe_safety()
    assert payload["dry_run"] is True
    assert payload["messages_sent"] == 0
    assert payload["send_implemented"] is False
    assert payload["banner"] == "DRY RUN — NO MESSAGES SENT"


def test_api_exposes_no_send_route():
    """No HTTP route in the app may perform an outbound send."""
    from app.main import app

    forbidden = ("send", "dispatch", "deliver", "smtp", "webhook")
    paths = [route.path for route in app.routes]
    offenders = [
        p
        for p in paths
        if any(word in p.lower() for word in forbidden) and "retry" not in p.lower()
    ]
    assert offenders == [], f"Unexpected send-like routes: {offenders}"
