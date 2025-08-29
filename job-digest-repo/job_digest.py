#!/usr/bin/env python3
"""
Weekly Job Digest
- Reads multiple RSS feeds (InfoJobs, Empléate/SEPE, etc.)
- Filters by keywords and locations
- Deduplicates
- Builds an HTML + plain-text digest
- Sends via SMTP

Usage:
  python job_digest.py --config config.yaml
Environment variables for SMTP (recommended):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_STARTTLS=1 (default) or 0
"""

import argparse
import datetime as dt
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional
import feedparser
import re
from urllib.parse import urlparse

# ---------- Utilities ----------

MADRID_TZ = dt.timezone(dt.timedelta(hours=2))  # Europe/Madrid in summer (CEST). Override via --tz if needed.

def parse_date(entry) -> Optional[dt.datetime]:
    # feedparser normalizes dates into 'published_parsed' or 'updated_parsed' if available
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return dt.datetime(*t[:6], tzinfo=dt.timezone.utc).astimezone(MADRID_TZ)
    return None

def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def contains_any(text: str, needles: List[str]) -> bool:
    if not needles:
        return True
    text_l = text.lower()
    return any(n.lower() in text_l for n in needles)

def contains_none(text: str, needles: List[str]) -> bool:
    if not needles:
        return True
    text_l = text.lower()
    return all(n.lower() not in text_l for n in needles)

# ---------- Models ----------

@dataclass
class JobItem:
    title: str
    link: str
    summary: str
    location: str
    source: str
    published: Optional[dt.datetime]

# ---------- Core ----------

def fetch_feed(url: str) -> List[JobItem]:
    d = feedparser.parse(url)
    items: List[JobItem] = []
    src = urlparse(url).netloc
    for e in d.entries:
        title = normalize_text(e.get('title', ''))
        link = e.get('link', '')
        summary = normalize_text(e.get('summary', '') or e.get('description', ''))
        # Try to extract location if present in tags or summary
        location = ''
        if 'tags' in e and e.tags:
            location = ', '.join(t.get('term','') for t in e.tags if t.get('term'))
        # Some feeds include location in title like "[Pozuelo] ..."; attempt a simple heuristic
        m = re.search(r'\[(.*?)\]', title)
        if m and not location:
            location = m.group(1)
        items.append(JobItem(title=title, link=link, summary=summary, location=location, source=src, published=parse_date(e)))
    return items

def dedupe(items: List[JobItem]) -> List[JobItem]:
    seen = set()
    out = []
    for it in items:
        key = (it.title.lower(), it.link.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def within_days(items: List[JobItem], days: int) -> List[JobItem]:
    if days <= 0:
        return items
    cutoff = dt.datetime.now(MADRID_TZ) - dt.timedelta(days=days)
    out = []
    for it in items:
        if it.published is None:
            # Keep items with unknown date (some feeds omit dates)
            out.append(it)
        elif it.published >= cutoff:
            out.append(it)
    return out

def filter_items(items: List[JobItem], include_keywords: List[str], include_locations: List[str], exclude_keywords: List[str]) -> List[JobItem]:
    out = []
    for it in items:
        haystack = " | ".join([it.title, it.summary, it.location])
        if not contains_any(haystack, include_keywords):
            continue
        if include_locations and not contains_any(haystack, include_locations):
            continue
        if not contains_none(haystack, exclude_keywords):
            continue
        out.append(it)
    return out

def render_html(items: List[JobItem], header: str) -> str:
    rows = []
    for it in items:
        date_str = it.published.strftime('%Y-%m-%d %H:%M') if it.published else 'Fecha no disponible'
        rows.append(f"""
            <tr>
              <td style="padding:8px;border-bottom:1px solid #eee;"><a href="{it.link}">{it.title}</a></td>
              <td style="padding:8px;border-bottom:1px solid #eee;">{it.location or "-"}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;">{it.source}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap;">{date_str}</td>
            </tr>
        """)
    table = "\n".join(rows) if rows else '<tr><td colspan="4" style="padding:12px;">No se han encontrado ofertas con los filtros.</td></tr>'
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{header}</title>
</head>
<body style="font-family: Arial, sans-serif;">
  <h2>{header}</h2>
  <table style="border-collapse:collapse;width:100%;max-width:900px;">
    <thead>
      <tr>
        <th style="text-align:left;padding:8px;border-bottom:2px solid #333;">Oferta</th>
        <th style="text-align:left;padding:8px;border-bottom:2px solid #333;">Ubicación</th>
        <th style="text-align:left;padding:8px;border-bottom:2px solid #333;">Fuente</th>
        <th style="text-align:left;padding:8px;border-bottom:2px solid #333;">Fecha</th>
      </tr>
    </thead>
    <tbody>
      {table}
    </tbody>
  </table>
  <p style="margin-top:20px;font-size:12px;color:#666;">Generado automáticamente. Ajusta filtros en config.yaml.</p>
</body>
</html>"""

def render_text(items: List[JobItem], header: str) -> str:
    if not items:
        return header + "\n\n(No se han encontrado ofertas con los filtros.)\n"
    lines = [header, ""]
    for it in items:
        date_str = it.published.strftime('%Y-%m-%d %H:%M') if it.published else 'Fecha no disponible'
        lines.append(f"- {it.title} — {it.location or '-'} — {it.source} — {date_str}\n  {it.link}")
    return "\n".join(lines)

def send_email(subject: str, html_body: str, text_body: str, to_email: str, from_email: str):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    part1 = MIMEText(text_body, 'plain', 'utf-8')
    part2 = MIMEText(html_body, 'html', 'utf-8')
    msg.attach(part1)
    msg.attach(part2)

    host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    port = int(os.environ.get('SMTP_PORT', '587'))
    user = os.environ.get('SMTP_USER')
    pwd  = os.environ.get('SMTP_PASS')
    use_starttls = os.environ.get('SMTP_STARTTLS', '1') != '0'

    if not (user and pwd):
        raise RuntimeError("Faltan credenciales SMTP en variables de entorno SMTP_USER / SMTP_PASS.")

    if use_starttls:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(user, pwd)
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(host, port) as server:
            server.login(user, pwd)
            server.send_message(msg)

def run(config: Dict[str, Any], tz_offset_hours: Optional[int] = None):
    global MADRID_TZ
    if tz_offset_hours is not None:
        MADRID_TZ = dt.timezone(dt.timedelta(hours=tz_offset_hours))

    feeds: List[str] = config.get('feeds', [])
    include_keywords: List[str] = config.get('include_keywords', [])
    include_locations: List[str] = config.get('include_locations', [])
    exclude_keywords: List[str] = config.get('exclude_keywords', [])
    lookback_days: int = int(config.get('lookback_days', 7))

    all_items: List[JobItem] = []
    for url in feeds:
        try:
            all_items.extend(fetch_feed(url))
        except Exception as e:
            print(f"[WARN] Error leyendo feed {url}: {e}")

    all_items = dedupe(all_items)
    recent = within_days(all_items, lookback_days)
    filtered = filter_items(recent, include_keywords, include_locations, exclude_keywords)

    # Sort by date desc then title
    filtered.sort(key=lambda x: (x.published or dt.datetime.min.replace(tzinfo=MADRID_TZ)), reverse=True)

    header = config.get('header', 'Resumen semanal de ofertas')
    subject = config.get('subject', 'Ofertas semanales (zona oeste CM)')
    to_email = config.get('to_email')
    from_email = config.get('from_email', to_email)

    html_body = render_html(filtered, header)
    text_body = render_text(filtered, header)

    # Optionally write to files
    out_html = config.get('output_html')
    out_txt = config.get('output_txt')
    if out_html:
        with open(out_html, 'w', encoding='utf-8') as f:
            f.write(html_body)
    if out_txt:
        with open(out_txt, 'w', encoding='utf-8') as f:
            f.write(text_body)

    # Send email if configured
    if to_email:
        send_email(subject, html_body, text_body, to_email, from_email)
        print(f"[OK] Enviado a {to_email} con {len(filtered)} ofertas.")
    else:
        print("[INFO] 'to_email' no definido en config; no se envía correo.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, help='Ruta al config.yaml')
    parser.add_argument('--tz', type=int, help='Desplazamiento horario en horas (por defecto CEST=+2 en verano).')
    args = parser.parse_args()

    import yaml
    with open(args.config, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    run(cfg, tz_offset_hours=args.tz)

if __name__ == '__main__':
    main()
