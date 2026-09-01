"""Pure rendering seam for localized User magic-link email copy."""

from __future__ import annotations

import html
from dataclasses import dataclass

from magic_link_locales import MAGIC_LINK_TRANSLATIONS, normalize_magic_link_locale


@dataclass(frozen=True)
class RenderedMagicLinkEmail:
    """The localized values needed by the SMTP adapter."""

    subject: str
    html: str
    locale: str


_RTL_LOCALES = frozenset({"ar", "fa", "he"})


def render_magic_link_email(
    locale: object,
    display_name: str,
    verify_url: str,
    minutes: int = 15,
) -> RenderedMagicLinkEmail:
    """Render a magic-link email without reading request, browser, or server locale state."""
    normalized_locale = normalize_magic_link_locale(locale)
    messages = MAGIC_LINK_TRANSLATIONS[normalized_locale]
    # Header values must not receive CR/LF from an operator-configured display
    # name. The HTML representation is escaped separately below.
    safe_display_name = str(display_name).replace("\r", " ").replace("\n", " ")
    escaped_display_name = html.escape(safe_display_name)
    escaped_verify_url = html.escape(str(verify_url), quote=True)
    html_values = {
        "display_name": escaped_display_name,
        "minutes": str(minutes),
        "verify_url": f'<bdi dir="ltr">{escaped_verify_url}</bdi>',
    }

    copy = {
        field: messages[field].format(**html_values)
        for field in messages
        if field != "subject"
    }
    subject = messages["subject"].format(
        display_name=safe_display_name,
        minutes=str(minutes),
        verify_url=str(verify_url),
    )
    direction = "rtl" if normalized_locale in _RTL_LOCALES else "ltr"
    body_direction = "direction: rtl; text-align: right;" if direction == "rtl" else ""
    html_body = f"""<!DOCTYPE html>
<html lang="{normalized_locale}" dir="{direction}">
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; color: #333; {body_direction}">
    <div style="max-width: 480px; margin: 0 auto;">
        <h2 style="color: #333; margin-bottom: 24px;"><bdi dir="auto">{copy['heading']}</bdi></h2>
        <p style="margin-bottom: 12px;">{copy['explanation']}</p>
        <p style="margin-bottom: 24px;">{copy['expiry']}</p>
        <a href="{escaped_verify_url}"
           style="display: inline-block; background: #3B82F6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500;">
            <bdi dir="auto">{copy['button']}</bdi>
        </a>
        <p style="margin-top: 24px; font-size: 14px; color: #666;">
            {copy['unsolicited']}
        </p>
        <p style="margin-top: 24px; font-size: 12px; color: #999;">
            {copy['copy_link']}
        </p>
    </div>
</body>
</html>
"""
    return RenderedMagicLinkEmail(
        subject=subject,
        html=html_body,
        locale=normalized_locale,
    )
