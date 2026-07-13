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


def _click_first_visible(page: Page, selectors: list[str], timeout: int = 3000) -> bool:
    """Clicca il primo selettore visibile, evitando dipendenze da un solo markup Argo."""
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.click()
            return True
        except Exception:
            continue
    return False


def _navigate_to_teachers(page: Page) -> bool:
    """Apre Servizi Classe → Docenti Classe."""
    try:
        if not _click_first_visible(
            page,
            [
                'div.btl-accordionItem-head[aria-label="Servizi Classe"]',
                'div.btl-accordionItem[title="Servizi Classe"] .btl-accordionItem-head',
                '[aria-label="Servizi Classe"]',
            ],
            timeout=5000,
        ):
            logger.warning("Menu Servizi Classe non trovato")
            return False

        page.wait_for_timeout(500)
        if not _click_first_visible(
            page,
            [
                '#menu-serviziclasse\\:docenti-classe-famiglia',
                'span.btl-button[title="Docenti Classe"]',
                '[aria-label="Docenti Classe"][role="button"]',
                '[title="Docenti Classe"]',
                'text="Docenti Classe"',
            ],
            timeout=5000,
        ):
            logger.warning("Voce Docenti Classe non trovata")
            return False

        page.wait_for_timeout(1000)
        try:
            # La griglia Argo separa intestazioni e dati in due tabelle: attendiamo
            # una riga docente reale, non una qualsiasi tabella già presente.
            page.wait_for_selector(
                'div.btl-listGrid[id*="docentiClasse"] '
                '.btl-grid-dataViewContainer span[id$=":nominativo"]',
                timeout=5000,
            )
        except Exception:
            # Fallback per eventuali versioni di Argo con una tabella tradizionale.
            page.wait_for_selector("table, div.btl-table", timeout=5000)
        return True
    except Exception as exc:
        logger.error("Errore durante la navigazione ai docenti: %s", exc)
        return False


def _parse_teachers_table(page: Page) -> list[dict]:
    """Estrae nome e materia dalla pagina Docenti Classe."""
    teachers: list[dict] = []
    seen: set[tuple[str, str]] = set()

    # Argo attuale usa una btl-listGrid: intestazioni e dati sono in tabelle
    # separate, mentre nome e materie hanno id con suffissi stabili.
    argo_rows = page.locator(
        'div.btl-listGrid[id*="docentiClasse"] '
        '.btl-grid-dataViewContainer tbody tr[rowid]'
    ).all()
    for row in argo_rows:
        name_locator = row.locator('span[id$=":nominativo"]').first
        if name_locator.count() == 0:
            continue

        name = " ".join(name_locator.inner_text().split())
        subject_locator = row.locator('span[id$=":materie"]').first
        subject = (
            " ".join(subject_locator.inner_text().split())
            if subject_locator.count() > 0
            else ""
        )
        if not name:
            continue

        key = (name.casefold(), subject.casefold())
        if key in seen:
            continue
        seen.add(key)
        teachers.append({"name": name, "subject": subject or None})

    for table in page.locator("table, div.btl-table").all():
        rows = table.locator("tr").all()
        if not rows:
            continue

        headers = [
            cell.inner_text().strip().lower()
            for cell in rows[0].locator("th, td").all()
        ]
        teacher_index = next(
            (i for i, value in enumerate(headers) if any(word in value for word in ("docente", "professore", "insegnante", "nominativo"))),
            None,
        )
        subject_index = next(
            (i for i, value in enumerate(headers) if any(word in value for word in ("materia", "materie", "disciplina", "insegnamento"))),
            None,
        )

        # Ignora le altre tabelle della pagina (ad esempio le prenotazioni esistenti).
        if teacher_index is None:
            continue

        for row in rows[1:]:
            cells = row.locator("td").all()
            if teacher_index >= len(cells):
                continue
            name = " ".join(cells[teacher_index].inner_text().split())
            subject = ""
            if subject_index is not None and subject_index < len(cells):
                subject = " ".join(cells[subject_index].inner_text().split())
            if not name:
                continue
            key = (name.casefold(), subject.casefold())
            if key in seen:
                continue
            seen.add(key)
            teachers.append({"name": name, "subject": subject or None})

    # Alcune versioni di Argo mostrano il docente in una select anziché in tabella.
    if not teachers:
        teacher_selects = page.locator(
            'select[name*="docent" i], select[id*="docent" i], '
            'select[aria-label*="docent" i], select[name*="professor" i]'
        ).all()
        for select in teacher_selects:
            for option in select.locator("option").all():
                name = " ".join(option.inner_text().split())
                value = (option.get_attribute("value") or "").strip()
                if not name or not value or "selezion" in name.casefold():
                    continue
                key = (name.casefold(), "")
                if key in seen:
                    continue
                seen.add(key)
                teachers.append({"name": name, "subject": None})

    logger.info("Estratti %d docenti", len(teachers))
    return teachers


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


def estrai_docenti_con_credenziali(
    codice_scuola: str,
    username: str,
    password: str,
) -> list[dict]:
    """Accede ad Argo ed estrae i docenti della classe."""
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
            if not _navigate_to_teachers(page):
                return []
            return _parse_teachers_table(page)
        except Exception as exc:
            logger.error("Errore generale nello scraper docenti: %s", exc)
            return []
        finally:
            browser.close()
