from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import unittest
from string import Formatter
from pathlib import Path

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DummySentenceTransformer:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class MagicLinkLocalizationTest(unittest.TestCase):
    def test_translation_catalog_covers_exact_control_plane_locale_set_and_placeholders(self) -> None:
        from magic_link_locales import (
            MAGIC_LINK_TRANSLATIONS,
            MAGIC_LINK_TRANSLATION_FIELDS,
            SUPPORTED_MAGIC_LINK_LOCALES,
        )
        from models import SUPPORTED_DEFAULT_LANGUAGES

        self.assertEqual(set(MAGIC_LINK_TRANSLATIONS), SUPPORTED_DEFAULT_LANGUAGES)
        self.assertEqual(set(SUPPORTED_MAGIC_LINK_LOCALES), SUPPORTED_DEFAULT_LANGUAGES)
        self.assertEqual(
            set(MAGIC_LINK_TRANSLATION_FIELDS),
            {"subject", "heading", "explanation", "button", "expiry", "unsolicited", "copy_link"},
        )
        expected_placeholders = {
            "subject": {"display_name"},
            "heading": {"display_name"},
            "explanation": set(),
            "button": {"display_name"},
            "expiry": {"minutes"},
            "unsolicited": set(),
            "copy_link": {"verify_url"},
        }
        for locale, messages in MAGIC_LINK_TRANSLATIONS.items():
            with self.subTest(locale=locale):
                for field in MAGIC_LINK_TRANSLATION_FIELDS:
                    placeholders = {
                        field_name
                        for _, field_name, _, _ in Formatter().parse(messages[field])
                        if field_name is not None
                    }
                    self.assertEqual(placeholders, expected_placeholders[field])

    def test_every_advertised_locale_renders_without_unresolved_or_unknown_placeholders(self) -> None:
        from magic_link_email import render_magic_link_email
        from magic_link_locales import MAGIC_LINK_TRANSLATIONS, validate_magic_link_translation_catalog

        validate_magic_link_translation_catalog()
        for locale in MAGIC_LINK_TRANSLATIONS:
            with self.subTest(locale=locale):
                rendered = render_magic_link_email(locale, "Example", "https://example.test/verify?token=token")
                self.assertNotIn("{", rendered.subject)
                self.assertNotIn("}", rendered.subject)
                self.assertNotIn("{", rendered.html)
                self.assertNotIn("}", rendered.html)

    def test_subject_keeps_plain_identity_and_strips_header_newlines_while_html_stays_escaped(self) -> None:
        from magic_link_email import render_magic_link_email

        rendered = render_magic_link_email(
            "en",
            'A & B <Q> "D"\r\nBcc: attacker@example.test',
            "https://example.test/verify?token=token-123",
        )

        self.assertEqual(
            rendered.subject,
            'Sign in to A & B <Q> "D"  Bcc: attacker@example.test',
        )
        self.assertIn("A &amp; B &lt;Q&gt; &quot;D&quot;  Bcc: attacker@example.test", rendered.html)
        self.assertNotIn("\r", rendered.subject)
        self.assertNotIn("\n", rendered.subject)

    def test_missing_and_invalid_locale_use_english_without_changing_renderer_contract(self) -> None:
        from magic_link_locales import normalize_magic_link_locale

        self.assertEqual(normalize_magic_link_locale(None), "en")
        self.assertEqual(normalize_magic_link_locale(""), "en")
        self.assertEqual(normalize_magic_link_locale("not-a-locale"), "en")
        self.assertEqual(normalize_magic_link_locale(42), "en")
        self.assertEqual(normalize_magic_link_locale(" es "), "es")

    def test_spanish_email_localizes_all_static_copy_and_keeps_url(self) -> None:
        from magic_link_email import render_magic_link_email

        rendered = render_magic_link_email(
            locale="es",
            display_name="FreeThem",
            verify_url="https://example.test/verify?token=token-123",
        )

        self.assertEqual(rendered.subject, "Inicia sesión en FreeThem")
        for expected in (
            "Inicia sesión en FreeThem",
            "Haz clic en el botón de abajo para iniciar sesión.",
            "Este enlace caducará en 15 minutos.",
            "Iniciar sesión en FreeThem",
            "Si no solicitaste este correo electrónico, puedes ignorarlo sin problemas.",
            "O copia este enlace:",
            "https://example.test/verify?token=token-123",
        ):
            self.assertIn(expected, rendered.html)

    def test_arabic_email_is_rtl_safe_and_escapes_interpolated_values(self) -> None:
        from magic_link_email import render_magic_link_email

        rendered = render_magic_link_email(
            locale="ar",
            display_name="<Free & Safe>",
            verify_url="https://example.test/verify?token=a&b=1",
        )

        self.assertIn('<html lang="ar" dir="rtl">', rendered.html)
        self.assertIn("تسجيل الدخول إلى &lt;Free &amp; Safe&gt;", rendered.html)
        self.assertIn('<bdi dir="auto">', rendered.html)
        self.assertIn('<bdi dir="ltr">https://example.test/verify?token=a&amp;b=1</bdi>', rendered.html)
        self.assertIn("انقر على الزر أدناه لتسجيل الدخول.", rendered.html)
        self.assertIn("إذا لم تطلب هذا البريد الإلكتروني، يمكنك تجاهله بأمان.", rendered.html)
        self.assertIn("https://example.test/verify?token=a&amp;b=1", rendered.html)
        self.assertNotIn("<Free & Safe>", rendered.html)

    def test_non_priority_czech_email_is_translated(self) -> None:
        from magic_link_email import render_magic_link_email

        rendered = render_magic_link_email(
            locale="cs",
            display_name="Enclave",
            verify_url="https://example.test/verify?token=token-123",
        )

        self.assertEqual(rendered.subject, "Přihlaste se do Enclave")
        self.assertIn("Kliknutím na tlačítko níže se přihlásíte.", rendered.html)
        self.assertIn("Platnost tohoto odkazu vyprší za 15 minut.", rendered.html)
        self.assertNotIn("Sign in to Enclave", rendered.html)

    def test_request_accepts_locale_and_passes_it_to_email_sender(self) -> None:
        self._set_up_app()
        try:
            captured: list[tuple[str, str, object]] = []

            def record(to_email: str, token: str, locale: object = None) -> bool:
                captured.append((to_email, token, locale))
                return True

            self.auth.send_magic_link_email = record
            response = self.client.post(
                "/auth/magic-link",
                json={"email": "known@example.com", "name": "Known User", "locale": "es"},
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                "success": True,
                "message": "If this address can sign in, we'll send a magic link.",
            })
            self.assertEqual(captured[0][2], "es")
            self.assertEqual(
                self.auth.verify_magic_link_token(captured[0][1]),
                {"email": "known@example.com", "name": "Known User"},
            )
            self.assertEqual(self.auth.MAGIC_LINK_MAX_AGE, 15 * 60)
        finally:
            self._tear_down_app()

    def test_request_with_invalid_locale_falls_back_without_422(self) -> None:
        self._set_up_app()
        try:
            captured: list[object] = []

            def record(to_email: str, token: str, locale: object = None) -> bool:
                captured.append(locale)
                return True

            self.auth.send_magic_link_email = record
            response = self.client.post(
                "/auth/magic-link",
                json={"email": "known@example.com", "name": "Known User", "locale": "xx"},
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(captured, ["en"])
        finally:
            self._tear_down_app()

    def _set_up_app(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_secret_key = os.environ.get("SECRET_KEY")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        self._orig_sentence_transformers = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=DummySentenceTransformer
        )
        os.environ["SQLITE_PATH"] = str(self.db_path)
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import auth
        import database
        import main

        self.auth = importlib.reload(auth)
        self.database = importlib.reload(database)
        self.main = importlib.reload(main)
        self.database.init_schema()
        self.database.add_admin("a" * 64)
        self.database.mark_instance_setup_complete()
        self.database.create_user(email="known@example.com", name="Known User")
        self.client = TestClient(self.main.app)

    def _tear_down_app(self) -> None:
        self.main.app.dependency_overrides.clear()
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SECRET_KEY", self._orig_secret_key)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        if self._orig_sentence_transformers is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = self._orig_sentence_transformers
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
