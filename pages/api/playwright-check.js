import { chromium } from 'playwright';

export default async function handler(req, res) {
  try {
    const browser = await chromium.launch();
    await browser.close();
    res.status(200).json({ success: true });
  } catch (error) {
    console.error("Errore Playwright:", error);
    res.status(500).json({ error: error.message });
  }
}