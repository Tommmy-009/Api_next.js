import unittest
from auth.jwt_handler import create_access_token, get_user_id_from_token
from jose import JWTError
from models.user import RegisterRequest
from scraper.argo import _parse_teachers_table
from scraper.credentials_crypto import decrypt_argo_password, encrypt_argo_password
from admin.router import _render_dashboard


class FakeLocator:
    def __init__(self, text="", children=None):
        self.text = text
        self.children = children or {}

    def all(self):
        return self.children.get("all", [])

    def locator(self, selector):
        return FakeLocator(children={"all": self.children.get(selector, [])})

    def inner_text(self, **_):
        return self.text

    @property
    def first(self):
        return self


class FakePage:
    def __init__(self, table):
        self.table = table

    def locator(self, selector):
        if selector.startswith('div.btl-listGrid'):
            return FakeLocator(children={"all": []})
        if selector == "table":
            return FakeLocator(children={"all": [self.table]})
        return FakeLocator(children={"all": []})


class TeacherParsingTests(unittest.TestCase):
    def test_parses_normalizes_and_deduplicates_html_table(self):
        headers = [FakeLocator("Docente"), FakeLocator("Materia")]
        rows = [
            FakeLocator(children={"td": [FakeLocator("Docente"), FakeLocator("Materia")]}),
            FakeLocator(children={"td": [FakeLocator("  Rossi   Mario "), FakeLocator(" Matematica ")]}),
            FakeLocator(children={"td": [FakeLocator("Rossi Mario"), FakeLocator("Matematica")]}),
            FakeLocator(children={"td": [FakeLocator("Bianchi Anna"), FakeLocator("")]}),
        ]
        table = FakeLocator(children={
            "thead th, tr:first-child th, tr:first-child td": headers,
            "tbody tr, tr": rows,
        })

        result = _parse_teachers_table(FakePage(table))

        self.assertEqual(result, [
            {"name": "Rossi Mario", "subject": "Matematica"},
            {"name": "Bianchi Anna", "subject": None},
        ])

    def test_empty_table_returns_empty_list(self):
        table = FakeLocator(children={
            "thead th, tr:first-child th, tr:first-child td": [FakeLocator("Docente")],
            "tbody tr, tr": [FakeLocator(children={"td": [FakeLocator("Docente")]})],
        })
        self.assertEqual(_parse_teachers_table(FakePage(table)), [])


class SecurityTests(unittest.TestCase):
    def test_jwt_rejects_non_uuid_subject(self):
        token, _ = create_access_token("00000000-0000-0000-0000-000000000001")
        self.assertEqual(get_user_id_from_token(token), "00000000-0000-0000-0000-000000000001")

        from auth.jwt_handler import jwt, settings
        invalid = jwt.encode(
            {"sub": "not-a-uuid", "type": "access"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with self.assertRaises(JWTError):
            get_user_id_from_token(invalid)

    def test_argo_password_is_encrypted_and_admin_never_renders_secrets(self):
        encrypted = encrypt_argo_password("argo-secret")
        self.assertNotEqual(encrypted, "argo-secret")
        self.assertEqual(decrypt_argo_password(encrypted), "argo-secret")

        html = _render_dashboard([{
            "id": "user",
            "email": "user@example.com",
            "name": None,
            "created_at": None,
            "updated_at": None,
            "email_confirmed_at": None,
            "last_sign_in_at": None,
            "argo_configured": True,
            "codice_scuola": "SC1",
            "argo_username": "user",
        }])
        self.assertNotIn("argo-secret", html)
        self.assertNotIn("password_hash", html)

    def test_registration_rejects_blank_password(self):
        with self.assertRaises(ValueError):
            RegisterRequest(email="user@example.com", password="   ")


if __name__ == "__main__":
    unittest.main()
