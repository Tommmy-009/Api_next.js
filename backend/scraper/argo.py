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

    try:

        _save_debug(page)

        logger.info("Tentativo apertura menu Servizi Classe...")

        accordion_selector = (
            'div.btl-accordionItem[title="Servizi Classe"]'
        )

        page.wait_for_selector(
            accordion_selector,
            timeout=10000
        )

        page.click(accordion_selector)

        page.wait_for_timeout(2000)

        logger.info("Menu Servizi Classe aperto")

        # ─────────────────────────────────────────────
        # Bottone PROMEMORIA
        # ─────────────────────────────────────────────

        promemoria_selector = (
            '#menu-serviziclasse\\:promemoria-famiglia'
        )

        page.wait_for_selector(
            promemoria_selector,
            timeout=10000
        )

        logger.info("Bottone Promemoria trovato")

        page.click(promemoria_selector)

        logger.info("Click su Promemoria eseguito")

        page.wait_for_timeout(4000)

        _save_debug(page)

        logger.info("Cerco la tabella verifiche...")

        table_selectors = [
            "table",
            "div.btl-table",
            "table.btl-table",
        ]

        for selector in table_selectors:

            try:

                page.wait_for_selector(
                    selector,
                    timeout=5000
                )

                logger.info(
                    f"Tabella trovata con selettore: {selector}"
                )

                return True

            except Exception:
                continue

        logger.error("Tabella NON trovata")

        return False

    except Exception as e:

        logger.error(
            f"Errore nell'espansione del menu: {e}"
        )

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