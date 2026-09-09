"""
scraper/argo.py — Scraper Argo con Playwright
Versione robusta con debug screenshot/html
"""

import os
import logging

from playwright.sync_api import sync_playwright, Page, Browser

logger = logging.getLogger(__name__)

DEBUG_SCRAPER = os.getenv("DEBUG_SCRAPER", "false").lower() == "true"

ARGO_BASE_URL = "https://www.portaleargo.it/argoweb/famiglia/"


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _click_first_available(page: Page, selectors: list[str], timeout: int = 5000) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.click()
            logger.info(f"Click eseguito con selettore: {selector}")
            return True
        except Exception:
            continue

    return False


def _wait_for_any_selector(page: Page, selectors: list[str], timeout: int = 5000) -> bool:
    for selector in selectors:
        try:
            page.wait_for_selector(selector, timeout=timeout)
            logger.info(f"Dati trovati con selettore: {selector}")
            return True
        except Exception:
            continue

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers debug
# ─────────────────────────────────────────────────────────────────────────────

def _save_debug(page: Page):
    """Salva screenshot + html per debug."""
    if not DEBUG_SCRAPER:
        return

    try:
        page.screenshot(path="/app/backend/debug.png", full_page=True)

        with open("/app/backend/debug.html", "w", encoding="utf-8") as f:
            f.write(page.content())

        logger.info("Debug HTML + screenshot salvati")

    except Exception as e:
        logger.error(f"Errore salvataggio debug: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Parsing tabella
# ─────────────────────────────────────────────────────────────────────────────

def _parse_promemoria_table(page: Page) -> list[dict]:
    """Estrae le verifiche/promemoria dalla tabella."""

    promemoria = []

    rows = page.locator("table tr").all()

    logger.info(f"Trovate {len(rows)} righe")

    for row in rows[1:]:

        cells = row.locator("td").all()

        if len(cells) < 3:
            continue

        try:
            data = cells[0].inner_text().strip()
            materia = cells[1].inner_text().strip()
            descrizione = cells[2].inner_text().strip()

        except Exception:
            continue

        # Filtri anti-rumore
        if not any([data, materia, descrizione]):
            continue

        if (
            "Alunno:" in data
            or "Classe:" in data
            or "Informiamo gli utenti" in data
        ):
            continue

        promemoria.append({
            "data": data,
            "materia": materia,
            "descrizione": descrizione,
        })

    logger.info(f"Estratti {len(promemoria)} promemoria")

    return promemoria


def _parse_teachers_table(page: Page) -> list[dict]:
    """Estrae i docenti della classe dalla vista Argo."""

    teachers: list[dict] = []
    seen: set[tuple[str, str | None]] = set()

    def add_teacher(name: str, subject: str | None = None):
        normalized_name = _normalize_text(name)
        normalized_subject = _normalize_text(subject)

        if not normalized_name:
            return

        item = {
            "name": normalized_name,
            "subject": normalized_subject or None,
        }
        key = (
            item["name"].casefold(),
            item["subject"].casefold() if item["subject"] else None,
        )

        if key in seen:
            return

        seen.add(key)
        teachers.append(item)

    # Struttura moderna Argo: griglia docentiClasse con celle nominativo/materie.
    modern_rows = page.locator(
        'div.btl-listGrid[id*="docentiClasse"] '
        '.btl-grid-dataViewContainer tbody tr[rowid]'
    ).all()

    logger.info(f"Trovate {len(modern_rows)} righe docenti nella griglia moderna")

    for row in modern_rows:
        try:
            name = row.locator('span[id$=":nominativo"]').first.inner_text(timeout=2000)
        except Exception:
            continue

        subject = None
        try:
            subject = row.locator('span[id$=":materie"]').first.inner_text(timeout=1000)
        except Exception:
            subject = None

        add_teacher(name, subject)

    if teachers:
        logger.info(f"Estratti {len(teachers)} docenti dalla griglia moderna")
        return teachers

    teacher_headers = (
        "docente",
        "professore",
        "insegnante",
        "nominativo",
    )
    subject_headers = (
        "materia",
        "materie",
        "disciplina",
        "insegnamento",
    )

    # Fallback: tabelle HTML tradizionali, accettate solo se le intestazioni
    # identificano esplicitamente una tabella docenti.
    tables = page.locator("table").all()
    logger.info(f"Trovate {len(tables)} tabelle HTML per fallback docenti")

    for table in tables:
        try:
            headers = [
                _normalize_text(cell.inner_text()).casefold()
                for cell in table.locator("thead th, tr:first-child th, tr:first-child td").all()
            ]
        except Exception:
            continue

        if not headers:
            continue

        teacher_index = next(
            (
                index
                for index, header in enumerate(headers)
                if any(token in header for token in teacher_headers)
            ),
            None,
        )
        subject_index = next(
            (
                index
                for index, header in enumerate(headers)
                if any(token in header for token in subject_headers)
            ),
            None,
        )

        if teacher_index is None:
            continue

        rows = table.locator("tbody tr, tr").all()
        for row in rows[1:]:
            cells = row.locator("td").all()
            if len(cells) <= teacher_index:
                continue

            try:
                name = cells[teacher_index].inner_text()
                subject = (
                    cells[subject_index].inner_text()
                    if subject_index is not None and len(cells) > subject_index
                    else None
                )
            except Exception:
                continue

            add_teacher(name, subject)

        if teachers:
            logger.info(f"Estratti {len(teachers)} docenti da tabella HTML")
            return teachers

    # Fallback estremo: select relative ai docenti.
    select_locators = page.locator(
        'select[name*="docent" i], select[id*="docent" i], '
        'select[name*="insegn" i], select[id*="insegn" i], '
        'select[name*="prof" i], select[id*="prof" i]'
    ).all()

    for select in select_locators:
        for option in select.locator("option").all():
            try:
                value = _normalize_text(option.inner_text())
            except Exception:
                continue

            lowered = value.casefold()
            if not value or lowered in {"seleziona", "scegli", "tutti", "tutte"}:
                continue

            add_teacher(value)

    logger.info(f"Estratti {len(teachers)} docenti totali")
    return teachers


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

def _do_login(
    page: Page,
    codice_scuola: str,
    username: str,
    password: str,
) -> bool:

    try:

        logger.info("Navigando alla pagina di login Argo...")

        page.goto(ARGO_BASE_URL)

        page.wait_for_load_state(
            "domcontentloaded",
            timeout=15000
        )

        logger.info("Compilando il form di login...")

        page.fill(
            'input[name="famiglia_customer_code"]',
            codice_scuola
        )

        page.fill(
            'input[name="username"]',
            username
        )

        page.fill(
            'input[name="password"]',
            password
        )

        page.click("button#accediBtn")

        page.wait_for_load_state(
            "domcontentloaded",
            timeout=15000
        )

        page.wait_for_timeout(3000)

        if page.url == ARGO_BASE_URL:
            logger.error("Login fallito")
            return False

        logger.info(f"Login OK — URL corrente: {page.url}")

        return True

    except Exception as e:

        logger.error(f"Errore login: {e}")

        return False


# ─────────────────────────────────────────────────────────────────────────────
# Navigazione promemoria
# ─────────────────────────────────────────────────────────────────────────────

def _navigate_to_promemoria(page: Page) -> bool:
    """Apre la pagina Promemoria della nuova SPA Argo.

    Il nuovo portale usa un router hash-based e non espone più gli ID
    ``btl-*`` del vecchio menu.
    """
    try:
        _save_debug(page)
        logger.info("Apertura pagina Promemoria Argo...")

        selectors = [
            'a[href="#/main/promemoria/"]',
            'a[role="link"][href*="/main/promemoria"]',
            'a:has-text("Promemoria")',
        ]
        if not _click_first_available(page, selectors, timeout=10000):
            logger.error("Link Promemoria non trovato")
            _save_debug(page)
            return False

        page.wait_for_timeout(1500)
        try:
            page.wait_for_url("**#/main/promemoria/**", timeout=10000)
        except Exception:
            # Alcune versioni della SPA aggiornano il contenuto senza far
            # scattare l'attesa URL di Playwright.
            pass

        data_selectors = [
            "table",
            "[role=table]",
            "tbody",
            "text=Promemoria",
        ]
        if _wait_for_any_selector(page, data_selectors, timeout=10000):
            _save_debug(page)
            return True

        logger.error("Dati Promemoria/verifiche non trovati")
        _save_debug(page)
        return False
    except Exception as e:
        logger.error(f"Errore apertura Promemoria: {e}")
        _save_debug(page)
        return False


def _navigate_to_teachers(page: Page) -> bool:
    try:
        _save_debug(page)

        logger.info("Apertura pagina Condivisione Argo per i docenti...")
        teacher_selectors = [
            'a[href="#/main/condivisione/"]',
            'a[role="link"][href*="/main/condivisione"]',
            'a:has-text("Condivisione")',
        ]
        if not _click_first_available(page, teacher_selectors, timeout=10000):
            logger.error("Link Condivisione non trovato")
            _save_debug(page)
            return False

        page.wait_for_timeout(1500)
        try:
            page.wait_for_url("**#/main/condivisione/**", timeout=10000)
        except Exception:
            pass

        data_selectors = [
            'div.btl-listGrid[id*="docentiClasse"]',
            ".btl-grid-dataViewContainer",
            'span[id$=":nominativo"]',
            "table",
            "[role=table]",
            "div.btl-table",
            'text=Condivisione',
        ]

        if _wait_for_any_selector(page, data_selectors, timeout=7000):
            _save_debug(page)
            return True

        logger.error("Dati docenti non trovati")
        _save_debug(page)
        return False

    except Exception as e:
        logger.error(f"Errore navigazione docenti: {e}")
        _save_debug(page)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Entry point pubblico
# ─────────────────────────────────────────────────────────────────────────────

def estrai_promemoria_con_credenziali(
    codice_scuola: str,
    username: str,
    password: str,
) -> list[dict]:

    with sync_playwright() as p:

        browser: Browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        context = browser.new_context(
            viewport={
                "width": 1400,
                "height": 900,
            }
        )

        page = context.new_page()

        try:

            ok = _do_login(
                page,
                codice_scuola,
                username,
                password,
            )

            if not ok:
                return []

            ok = _navigate_to_promemoria(page)

            if not ok:
                return []

            return _parse_promemoria_table(page)

        except Exception as e:

            logger.error(
                f"Errore generale scraper: {e}"
            )

            return []

        finally:

            browser.close()


def estrai_docenti_con_credenziali(
    codice_scuola: str,
    username: str,
    password: str,
) -> list[dict]:

    with sync_playwright() as p:
        browser: Browser | None = None
        context = None
        page = None

        try:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )

            context = browser.new_context(
                viewport={
                    "width": 1400,
                    "height": 900,
                }
            )

            page = context.new_page()

            ok = _do_login(
                page,
                codice_scuola,
                username,
                password,
            )

            if not ok:
                return []

            ok = _navigate_to_teachers(page)

            if not ok:
                return []

            return _parse_teachers_table(page)

        except Exception as e:
            logger.error(f"Errore generale scraper docenti: {e}")
            if page is not None:
                _save_debug(page)
            return []

        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass

            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass

            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
