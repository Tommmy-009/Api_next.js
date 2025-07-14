import { useEffect, useState } from 'react';

export default function Home() {
  const [status, setStatus] = useState('Loading...');

  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .then(data => setStatus(data.status))
      .catch(() => setStatus('Error'));
  }, []);

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>API Argo Famiglia - Next.js</h1>
      <p>Status: {status}</p>
      <div>
        <h2>Available Endpoints:</h2>
        <ul>
          <li><strong>GET /api/health</strong> - Health check</li>
          <li><strong>GET /api/promemoria</strong> - Estrai promemoria da Argo</li>
          <li><strong>GET /api/promemoria/db</strong> - Ottieni promemoria dal database</li>
          <li><strong>GET /api/promemoria/calendar</strong> - Ottieni eventi calendario</li>
          <li><strong>POST /api/argo/scrape</strong> - Scrape con credenziali da Supabase</li>
        </ul>
      </div>
    </div>
  );
}