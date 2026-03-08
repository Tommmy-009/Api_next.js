"""
scraper/argo.py — Port Python del lib/scraper.js originale
Usa Playwright sync API per fare scraping su portaleargo.it
"""
import os
import logging
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Browser

logger = logging.getLogger(__name__)

DEBUG_SCRAPER = os.getenv("DEBUG_SCRAPER", "false").lower() == "true"

ARGO_BASE_URL = "https://www.portaleargo.it/argoweb/famiglia/"


def _parse_promemoria_table(page: Page) -> list[dict]:
    """Estrae e filtra le righe dalla tabella dei promemoria."""
    promemoria = []

    if DEBUG_SCRAPER:
        try:
            table_locator = page.locator("table, div.btl-table").first
            print("SCRAPER HTML:\n" + table_locator.inner_html())
        except Exception as e:
            print(f"SCRAPER HTML ERROR: {e}")

    # Trova le righe con diversi selettori (stesso approccio del JS originale)
    rows = page.locator("table tr, div.btl-table tr").all()
    
    if DEBUG_SCRAPER:
        print(f"SCRAPER DEBUG:\nRows found: {len(rows)}")
    logger.info(f"Trovate {len(rows)} righe nella tabella")

    for i, row in enumerate(rows[1:], start=1):  # Salta header
        cells = row.locator("td").all()
        if len(cells) < 3:
            continue

        data = cells[0].inner_text().strip()
        materia = cells[1].inner_text().strip()
        descrizione = cells[2].inner_text().strip()

        # Filtri: stessa logica del JS
        if not any([data, materia, descrizione]):
            continue
        if (
            data.startswith("Alunno:")
            or data.startswith("Classe:")
            or "Informiamo gli utenti" in data
        ):
            continue

        if DEBUG_SCRAPER:
            print(f"Parsed test:\ndate={data}\nsubject={materia}\ndescription={descrizione}")

        promemoria.append(
            {"data": data, "materia": materia, "descrizione": descrizione}
        )

    if DEBUG_SCRAPER:
        print("SCRAPER DEBUG:\nParsed tests:")
        for p in promemoria:
            print(f"- {p['data']} {p['materia']}")

    logger.info(f"Estratti {len(promemoria)} promemoria validi")
    return promemoria


def _navigate_to_promemoria(page: Page) -> bool:
    """
    Naviga alla sezione Promemoria per Classe.
    Restituisce True se la tabella è stata trovata.
    """
    accordion_selector = 'div.btl-accordionItem[title="Servizi Classe"]'
    accordion_head = 'div.btl-accordionItem-head[aria-label="Servizi Classe"]'
    promemoria_btn = 'span.btl-button[title="Promemoria per Classe"]'

    try:
        page.wait_for_selector(accordion_selector, timeout=5000)
        page.click(accordion_head)
        page.wait_for_timeout(800)

        page.wait_for_selector(promemoria_btn, timeout=3000)
        page.click(promemoria_btn)
        page.wait_for_timeout(1000)

        # Cerca la tabella con diversi selettori
        table_selectors = [
            "table.btl-table",
            "table",
            "div[class*='table']",
            "div.btl-table",
        ]

        if DEBUG_SCRAPER:
            print("SCRAPER DEBUG:\nWaiting for table selector...")
        try:
            page.wait_for_selector("table", timeout=5000)
        except Exception:
            pass
        for sel in table_selectors:
            try:
                page.wait_for_selector(sel, timeout=2000)
                logger.info(f"Tabella trovata con selettore: {sel}")
                return True
            except Exception:
                continue

        logger.warning("Nessun selettore della tabella ha funzionato")
        return False

    except Exception as e:
        logger.error(f"Errore nell'espansione del menu: {e}")
        return False


def _do_login(page: Page, codice_scuola: str, username: str, password: str) -> bool:
    """
    Effettua il login su portaleargo.it.
    Restituisce True se il login è andato a buon fine.
    """
    try:
        logger.info("Navigando alla pagina di login Argo...")
        page.goto(ARGO_BASE_URL)
        page.wait_for_load_state("domcontentloaded", timeout=10000)

        logger.info("Compilando il form di login...")
        page.fill('input[name="famiglia_customer_code"]', codice_scuola)
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)
        page.click("button#accediBtn")
        page.wait_for_load_state("domcontentloaded", timeout=8000)
        page.wait_for_timeout(1500)

        # Controlla se siamo ancora sulla pagina di login
        if page.url == ARGO_BASE_URL:
            logger.error("Login fallito — URL invariato dopo il click")
            return False

        if DEBUG_SCRAPER:
            print("SCRAPER DEBUG:\nLogin successful")
        logger.info(f"Login OK — URL corrente: {page.url}")
        return True

    except Exception as e:
        logger.error(f"Errore durante il login: {e}")
        return False


def estrai_promemoria_con_credenziali(
    codice_scuola: str,
    username: str,
    password: str,
) -> list[dict]:
    """
    Lancia un browser Chromium headless, fa il login su portaleargo.it,
    naviga alla sezione Promemoria e restituisce la lista degli elementi.

    Args:
        codice_scuola: Codice scuola Argo (es. "SS12345")
        username: Username studente/famiglia
        password: Password

    Returns:
        Lista di dict con chiavi: data, materia, descrizione
        Lista vuota in caso di errore o nessun promemoria trovato.
    """
    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        try:
            if not _do_login(page, codice_scuola, username, password):
                return []

            if not _navigate_to_promemoria(page):
                return []

            return _parse_promemoria_table(page)

        except Exception as e:
            logger.error(f"Errore generale nello scraper: {e}")
            return []

        finally:
            browser.close()
