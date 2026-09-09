"""
admin/router.py — Dashboard admin per visione utenti e credenziali Argo
"""
from datetime import datetime
import html
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import settings
from database.db import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])
basic_auth = HTTPBasic()


def _require_admin(credentials: HTTPBasicCredentials = Depends(basic_auth)) -> str:
    username = settings.admin_dashboard_username
    password = settings.admin_dashboard_password

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Dashboard admin non configurata. "
                "Imposta ADMIN_DASHBOARD_USERNAME e ADMIN_DASHBOARD_PASSWORD."
            ),
        )

    is_valid = (
        secrets.compare_digest(credentials.username, username)
        and secrets.compare_digest(credentials.password, password)
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali admin non valide",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


def _load_admin_users(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                u.id,
                u.email,
                u.created_at,
                u.updated_at,
                u.email_confirmed_at,
                u.last_sign_in_at,
                up.name,
                ac.codice_scuola,
                ac.username AS argo_username
            FROM auth.users u
            LEFT JOIN public.user_profiles up
                ON up.user_id = u.id
            LEFT JOIN public.argo_credentials ac
                ON ac.user_id = u.id
            ORDER BY u.created_at DESC NULLS LAST, u.email ASC
            """
        )
    ).mappings().all()

    result = []
    for row in rows:
        result.append(
            {
                "id": str(row["id"]),
                "email": row["email"],
                "name": row["name"],
                "created_at": _format_datetime(row["created_at"]),
                "updated_at": _format_datetime(row["updated_at"]),
                "email_confirmed_at": _format_datetime(row["email_confirmed_at"]),
                "last_sign_in_at": _format_datetime(row["last_sign_in_at"]),
                "argo_configured": bool(row["codice_scuola"] and row["argo_username"]),
                "codice_scuola": row["codice_scuola"],
                "argo_username": row["argo_username"],
            }
        )

    return result


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _render_dashboard(users: list[dict]) -> str:
    rows_html = []
    for user in users:
        rows_html.append(
            """
            <tr>
                <td>{email}</td>
                <td>{name}</td>
                <td><code>{user_id}</code></td>
                <td>{argo_status}</td>
                <td>{codice_scuola}</td>
                <td>{argo_username}</td>
                <td>{created_at}</td>
                <td>{last_sign_in_at}</td>
            </tr>
            """.format(
                email=_safe(user["email"]),
                name=_safe(user["name"]),
                user_id=_safe(user["id"]),
                argo_status="Configurato" if user["argo_configured"] else "Non configurato",
                codice_scuola=_safe(user["codice_scuola"]),
                argo_username=_safe(user["argo_username"]),
                created_at=_safe(user["created_at"]),
                last_sign_in_at=_safe(user["last_sign_in_at"]),
            )
        )

    body_rows = "\n".join(rows_html) or """
        <tr>
            <td colspan="8">Nessun utente trovato.</td>
        </tr>
    """

    total_users = len(users)
    configured_argo = sum(1 for user in users if user["argo_configured"])

    return f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>UpNext Admin Dashboard</title>
        <style>
            :root {{
                color-scheme: light;
                --bg: #f4efe7;
                --panel: #fffdf9;
                --line: #d9cebf;
                --text: #201911;
                --muted: #6b5c4d;
                --accent: #b85c38;
                --accent-soft: #f3dfd3;
            }}
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                font-family: "Iowan Old Style", "Palatino Linotype", serif;
                background:
                    radial-gradient(circle at top right, #f8d7b7 0, transparent 28%),
                    linear-gradient(180deg, #f7f1e9 0%, var(--bg) 100%);
                color: var(--text);
            }}
            .wrap {{
                max-width: 1600px;
                margin: 0 auto;
                padding: 32px 20px 56px;
            }}
            .hero {{
                background: rgba(255, 253, 249, 0.88);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(184, 92, 56, 0.18);
                border-radius: 24px;
                padding: 24px;
                box-shadow: 0 20px 60px rgba(74, 48, 23, 0.08);
            }}
            h1 {{
                margin: 0 0 10px;
                font-size: clamp(32px, 5vw, 54px);
                line-height: 0.95;
                letter-spacing: -0.03em;
            }}
            p {{
                margin: 0;
                color: var(--muted);
                font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 14px;
                margin-top: 20px;
            }}
            .stat {{
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 18px;
                padding: 16px;
            }}
            .stat strong {{
                display: block;
                font-size: 28px;
                color: var(--accent);
            }}
            .table-card {{
                margin-top: 22px;
                background: rgba(255, 253, 249, 0.95);
                border: 1px solid var(--line);
                border-radius: 24px;
                overflow: hidden;
                box-shadow: 0 20px 60px rgba(74, 48, 23, 0.08);
            }}
            .table-scroll {{
                overflow: auto;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                min-width: 1320px;
                font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }}
            th, td {{
                padding: 14px 16px;
                border-bottom: 1px solid var(--line);
                text-align: left;
                vertical-align: top;
                font-size: 14px;
            }}
            th {{
                position: sticky;
                top: 0;
                background: var(--panel);
                z-index: 1;
                font-size: 12px;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: var(--muted);
            }}
            tr:hover td {{
                background: #fff7ef;
            }}
            code {{
                font-family: "SFMono-Regular", "SF Mono", Consolas, monospace;
                font-size: 12px;
                white-space: pre-wrap;
                word-break: break-word;
            }}
            .note {{
                margin-top: 12px;
                font-size: 13px;
            }}
            .pill {{
                display: inline-block;
                padding: 5px 10px;
                border-radius: 999px;
                background: var(--accent-soft);
                color: var(--accent);
                font-weight: 600;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <section class="hero">
                <span class="pill">Admin</span>
                <h1>Utenti UpNext</h1>
                <p>Vista amministrativa dello stato degli account e delle credenziali Argo.</p>
                <div class="stats">
                    <div class="stat">
                        <strong>{total_users}</strong>
                        Utenti registrati
                    </div>
                    <div class="stat">
                        <strong>{configured_argo}</strong>
                        Account Argo configurati
                    </div>
                    <div class="stat">
                        <strong>{total_users - configured_argo}</strong>
                        Senza Argo
                    </div>
                </div>
                <p class="note">Le password non vengono mai mostrate nella dashboard.</p>
            </section>

            <section class="table-card">
                <div class="table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Email</th>
                                <th>Nome</th>
                                <th>User ID</th>
                                <th>Argo</th>
                                <th>Codice Scuola</th>
                                <th>Username Argo</th>
                                <th>Creato il</th>
                                <th>Ultimo login</th>
                            </tr>
                        </thead>
                        <tbody>
                            {body_rows}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    </body>
    </html>
    """


def _safe(value: str | None) -> str:
    if value is None:
        return "—"
    return html.escape(str(value))


@router.get("/users", response_class=HTMLResponse, summary="Dashboard utenti admin")
def admin_users_dashboard(
    _: str = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    users = _load_admin_users(db)
    return HTMLResponse(_render_dashboard(users))


@router.get("/users.json", summary="Elenco utenti admin in JSON")
def admin_users_json(
    _: str = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    users = _load_admin_users(db)
    return {
        "total": len(users),
        "users": users,
    }
