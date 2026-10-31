"""Global dry-run / no-send guard.

Milestone 1 and the initial prototype never deliver a message to a real person.
This module is the single place where that is enforced: every channel's send
function raises instead of transmitting anything. The UI banner is decoration;
this is the actual control.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .config import get_settings


class Channel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    LINKEDIN = "linkedin"
    SOCIAL = "social"
    WEBSITE_FORM = "website_form"


class SendNotPermittedError(RuntimeError):
    """Raised whenever code attempts a real outbound message."""


@dataclass(frozen=True)
class DryRunDecision:
    """Result of the safety evaluation. Never performs I/O."""

    channel: str
    would_send: bool  # always False while DRY_RUN is on
    result: str  # "BLOCKED" | "WOULD PASS"
    reason: str
    dry_run: bool


def is_dry_run() -> bool:
    return get_settings().dry_run


def describe_safety() -> dict:
    """Report the safety state for /health and the UI banner."""
    settings = get_settings()
    return {
        "dry_run": settings.dry_run,
        "messages_sent": 0,
        "send_implemented": False,
        "banner": "DRY RUN — NO MESSAGES SENT",
        "detail": (
            "No email, SMS, LinkedIn/social or website-form message can be sent "
            "from this build. Send functions raise SendNotPermittedError."
        ),
    }


def evaluate_outreach(channel: Channel | str, *, approved: bool = False) -> DryRunDecision:
    """Dry-run safety evaluation: reports what *would* happen, sends nothing.

    Deliberately side-effect free so the UI can render a pass/blocked verdict.
    """
    channel = Channel(channel)
    if not approved:
        return DryRunDecision(
            channel=str(channel),
            would_send=False,
            result="BLOCKED",
            reason="Human approval is missing for this draft.",
            dry_run=is_dry_run(),
        )
    if is_dry_run():
        return DryRunDecision(
            channel=str(channel),
            would_send=False,
            result="BLOCKED",
            reason="Dry-run mode: this build is not permitted to send messages.",
            dry_run=True,
        )
    return DryRunDecision(
        channel=str(channel),
        would_send=False,
        result="BLOCKED",
        reason="No send provider is implemented in the prototype.",
        dry_run=is_dry_run(),
    )


def _blocked(channel: Channel, attempted_action: str) -> SendNotPermittedError:
    return SendNotPermittedError(
        f"Send blocked by the dry-run guard: attempted '{attempted_action}' on channel "
        f"'{channel}'. This build never delivers messages."
    )


def send_email(*_args, **_kwargs) -> None:
    raise _blocked(Channel.EMAIL, "send_email")


def send_sms(*_args, **_kwargs) -> None:
    raise _blocked(Channel.SMS, "send_sms")


def send_linkedin_message(*_args, **_kwargs) -> None:
    raise _blocked(Channel.LINKEDIN, "send_linkedin_message")


def send_social_message(*_args, **_kwargs) -> None:
    raise _blocked(Channel.SOCIAL, "send_social_message")


def submit_website_form(*_args, **_kwargs) -> None:
    raise _blocked(Channel.WEBSITE_FORM, "submit_website_form")


# Single registry so nothing can quietly bypass the guard.
SEND_FUNCTIONS = {
    Channel.EMAIL: send_email,
    Channel.SMS: send_sms,
    Channel.LINKEDIN: send_linkedin_message,
    Channel.SOCIAL: send_social_message,
    Channel.WEBSITE_FORM: submit_website_form,
}


def get_sender(channel: Channel | str):
    """Return the guarded sender for a channel. The returned callable always raises."""
    return SEND_FUNCTIONS[Channel(channel)]
