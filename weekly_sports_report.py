"""
Reporte Semanal de Deportes (HTML) - v3
=========================================

Ahora incluye varias ligas/competencias por deporte:

    Fútbol:
        - General (ESPN Colombia)
        - Premier League
        - La Liga
        - Champions League
        - Liga BetPlay (Colombia)

    NFL (Football Americano):
        - NFL
        - NCAA Football (Universitario)

    Voleibol:
        - General (ESPN Deportes)
        - NCAA Voleibol (Universitario)

Genera una página HTML (reporte_deportes.html) con:
    1. "Lo más relevante" arriba (lesiones y transferencias primero).
    2. Listado completo por deporte > categoría, mostrando la liga
       de origen de cada noticia.

NOTA: Algunas URLs de ligas específicas pueden cambiar con el tiempo
o no existir para todos los deportes. Si una liga falla, el script
simplemente la omite y sigue con las demás (no rompe el reporte).
Si ves "No se pudo obtener información" para una liga en particular,
puedes editar/borrar esa URL en el diccionario SOURCES de abajo.

Requisitos (instalar una sola vez):
    pip install requests beautifulsoup4

Uso:
    python weekly_sports_report.py
"""

import os
import re
import datetime
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------------------

# Estructura: deporte -> { nombre_liga: url }
SOURCES = {
    "Fútbol": {
        "General": "https://www.espn.com.co/futbol/",
        "Premier League": "https://www.espn.com.co/futbol/liga/_/nombre/eng.1",
        "La Liga": "https://www.espn.com.co/futbol/liga/_/nombre/esp.1",
        "Champions League": "https://www.espn.com.co/futbol/liga/_/nombre/uefa.champions",
        "Liga BetPlay (Colombia)": "https://www.espn.com.co/futbol/liga/_/nombre/col.1",
    },
    "NFL (Football Americano)": {
        "NFL": "https://www.espn.com/nfl/",
        "NCAA Football (Universitario)": "https://www.espn.com/college-football/",
    },
    "Voleibol": {
        "General": "https://espndeportes.espn.com/voleibol/",
        "NCAA Voleibol (Universitario)": "https://www.espn.com/college-volleyball/",
    },
}

# Palabras clave para clasificar cada titular
INJURY_KEYWORDS = [
    "injury", "injured", "out for", "ruled out", "sidelined",
    "lesión", "lesion", "lesionado", "baja por lesión", "se pierde",
    "dado de baja", "fuera de combate",
]

TRANSFER_KEYWORDS = [
    "transfer", "traded", "trade", "signs", "signing", "sign with",
    "agrees to", "deal", "free agent", "extension",
    "fichaje", "ficha por", "traspaso", "renovación", "renovacion",
    "renueva", "se va al", "nuevo equipo", "acuerdo",
]

OUTPUT_DIR = "reports"
HTML_FILENAME = "reporte_deportes.html"

TOP_N_RELEVANT = 4          # noticias destacadas por deporte en el resumen
MAX_PER_CATEGORY = 12       # noticias mostradas por categoría (todas las ligas combinadas)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}

# ---------------------------------------------------------------------------
# SCRAPING
# ---------------------------------------------------------------------------

def fetch_page(url: str):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as exc:
        print(f"    [AVISO] No se pudo descargar {url}: {exc}")
        return None


def get_base_url(url: str) -> str:
    match = re.match(r"(https?://[^/]+)", url)
    return match.group(1) if match else url


def extract_headlines(soup: BeautifulSoup, base_url: str) -> list[dict]:
    headlines = []
    seen_titles = set()

    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True)
        href = a_tag["href"]

        if not text or len(text) < 15:
            continue
        if text in seen_titles:
            continue

        skip_words = ["Log In", "Sign Up", "Watch", "Listen",
                       "Schedule", "Standings", "Scores", "Tickets"]
        if any(word.lower() == text.lower() for word in skip_words):
            continue

        if href.startswith("/"):
            href = base_url.rstrip("/") + href
        if not href.startswith("http"):
            continue

        seen_titles.add(text)
        headlines.append({"title": text, "link": href})

    return headlines


def classify_headline(title: str) -> str:
    lower_title = title.lower()

    for kw in INJURY_KEYWORDS:
        if kw in lower_title:
            return "Lesiones"

    for kw in TRANSFER_KEYWORDS:
        if kw in lower_title:
            return "Transferencias"

    return "Partidos / Noticias generales"


# ---------------------------------------------------------------------------
# PROCESAMIENTO
# ---------------------------------------------------------------------------

def get_sport_data(sport_name: str, leagues: dict) -> dict:
    """
    Descarga y combina la información de TODAS las ligas de un deporte.
    Devuelve categorías combinadas y un listado de qué ligas fallaron.
    """
    categories = {
        "Lesiones": [],
        "Transferencias": [],
        "Partidos / Noticias generales": [],
    }
    seen_global = set()  # evita repetir el mismo titular entre ligas
    failed_leagues = []
    successful_leagues = 0

    for league_name, url in leagues.items():
        soup = fetch_page(url)
        if soup is None:
            failed_leagues.append(league_name)
            continue

        successful_leagues += 1
        base_url = get_base_url(url)
        headlines = extract_headlines(soup, base_url)

        for item in headlines:
            if item["title"] in seen_global:
                continue
            seen_global.add(item["title"])

            item["league"] = league_name
            category = classify_headline(item["title"])
            categories[category].append(item)

    if successful_leagues == 0:
        return {"error": True, "relevant": [], "categories": {}, "failed_leagues": failed_leagues}

    # "Lo más relevante": lesiones primero, luego transferencias,
    # completando con noticias generales si hace falta.
    relevant = []
    for cat in ["Lesiones", "Transferencias", "Partidos / Noticias generales"]:
        for item in categories[cat]:
            if len(relevant) >= TOP_N_RELEVANT:
                break
            relevant.append(item)
        if len(relevant) >= TOP_N_RELEVANT:
            break

    return {
        "error": False,
        "relevant": relevant,
        "categories": categories,
        "failed_leagues": failed_leagues,
    }


# ---------------------------------------------------------------------------
# GENERACION DE HTML
# ---------------------------------------------------------------------------

HTML_HEAD = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reporte Semanal de Deportes</title>
<style>
    :root {
        --bg: #0f1115;
        --card: #1a1d24;
        --accent: #ff5a36;
        --accent2: #36c2ff;
        --text: #e8e8e8;
        --muted: #9aa0aa;
        --border: #2a2e37;
    }
    * { box-sizing: border-box; }
    body {
        margin: 0;
        font-family: 'Segoe UI', Arial, sans-serif;
        background: var(--bg);
        color: var(--text);
        line-height: 1.5;
    }
    header {
        background: linear-gradient(90deg, var(--accent), var(--accent2));
        padding: 30px 20px;
        text-align: center;
    }
    header h1 {
        margin: 0;
        font-size: 28px;
        color: #fff;
    }
    header p {
        margin: 6px 0 0;
        color: rgba(255,255,255,0.9);
        font-size: 14px;
    }
    .container {
        max-width: 900px;
        margin: 0 auto;
        padding: 20px;
    }
    .summary {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 30px;
    }
    .summary h2 {
        margin-top: 0;
        color: var(--accent);
        font-size: 20px;
    }
    .summary-item {
        padding: 8px 0;
        border-bottom: 1px solid var(--border);
    }
    .summary-item:last-child { border-bottom: none; }
    .summary-item a {
        color: var(--text);
        text-decoration: none;
        font-weight: 500;
    }
    .summary-item a:hover { color: var(--accent2); }
    .tag {
        display: inline-block;
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 12px;
        margin-right: 6px;
        font-weight: bold;
        text-transform: uppercase;
    }
    .tag-sport { background: var(--accent2); color: #00222e; }
    .tag-cat { background: var(--accent); color: #2e0a00; }
    .tag-league { background: #3a3f4b; color: var(--text); }

    .sport-section {
        margin-bottom: 35px;
    }
    .sport-section h2 {
        border-bottom: 2px solid var(--accent2);
        padding-bottom: 8px;
        font-size: 22px;
    }
    .failed-note {
        font-size: 12px;
        color: var(--muted);
        margin: 4px 0 0;
    }
    .category-block {
        margin-top: 18px;
    }
    .category-block h3 {
        font-size: 16px;
        color: var(--accent2);
        margin-bottom: 8px;
    }
    ul.news-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    ul.news-list li {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
    }
    ul.news-list a {
        color: var(--text);
        text-decoration: none;
    }
    ul.news-list a:hover {
        color: var(--accent2);
        text-decoration: underline;
    }
    .empty-msg {
        color: var(--muted);
        font-style: italic;
    }
    footer {
        text-align: center;
        color: var(--muted);
        font-size: 12px;
        padding: 20px;
    }
</style>
</head>
<body>
"""

HTML_FOOT = """
</body>
</html>
"""


def build_html(data_by_sport: dict) -> str:
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=7)

    parts = [HTML_HEAD]

    parts.append(f"""
<header>
    <h1>📰 Reporte Semanal de Deportes</h1>
    <p>Del {week_start.strftime('%d/%m/%Y')} al {today.strftime('%d/%m/%Y')}</p>
</header>
<div class="container">
""")

    # --- Resumen / Lo más relevante ---
    parts.append('<div class="summary"><h2>⭐ Lo más relevante de la semana</h2>')
    any_relevant = False
    for sport_name, data in data_by_sport.items():
        if data.get("error") or not data.get("relevant"):
            continue
        for item in data["relevant"]:
            any_relevant = True
            cat = classify_headline(item["title"])
            parts.append(f"""
<div class="summary-item">
    <span class="tag tag-sport">{sport_name}</span>
    <span class="tag tag-league">{item['league']}</span>
    <span class="tag tag-cat">{cat}</span>
    <a href="{item['link']}" target="_blank">{item['title']}</a>
</div>
""")
    if not any_relevant:
        parts.append('<p class="empty-msg">No se encontraron noticias destacadas esta semana.</p>')
    parts.append("</div>")

    # --- Secciones completas por deporte ---
    for sport_name, data in data_by_sport.items():
        parts.append(f'<div class="sport-section"><h2>{sport_name}</h2>')

        if data.get("error"):
            parts.append('<p class="empty-msg">⚠️ No se pudo obtener información de ninguna liga de este deporte.</p>')
            parts.append("</div>")
            continue

        failed = data.get("failed_leagues") or []
        if failed:
            parts.append(f'<p class="failed-note">⚠️ No se pudo obtener: {", ".join(failed)}</p>')

        categories = data["categories"]
        for cat_name, items in categories.items():
            parts.append(f'<div class="category-block"><h3>{cat_name}</h3>')
            if not items:
                parts.append('<p class="empty-msg">No se encontraron noticias en esta categoría.</p>')
            else:
                parts.append('<ul class="news-list">')
                for item in items[:MAX_PER_CATEGORY]:
                    parts.append(
                        f'<li><span class="tag tag-league">{item["league"]}</span> '
                        f'<a href="{item["link"]}" target="_blank">{item["title"]}</a></li>'
                    )
                parts.append("</ul>")
            parts.append("</div>")

        parts.append("</div>")

    parts.append("</div>")

    parts.append(f"""
<footer>
    Generado automáticamente el {today.strftime('%d/%m/%Y a las %H:%M')}.
</footer>
""")

    parts.append(HTML_FOOT)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("Generando reporte semanal de deportes...")

    data_by_sport = {}
    for sport_name, leagues in SOURCES.items():
        print(f"- {sport_name}:")
        for league_name in leagues:
            print(f"    - Descargando: {league_name} ...")
        data_by_sport[sport_name] = get_sport_data(sport_name, leagues)

    html_content = build_html(data_by_sport)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, HTML_FILENAME)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\nReporte guardado en: {filepath}")
    print("Listo. Abre ese archivo .html en tu navegador para verlo.")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# COMO AUTOMATIZARLO CADA SEMANA EN WINDOWS
# ---------------------------------------------------------------------------
#
# 1. Abre el "Programador de tareas" (Task Scheduler) desde el menú Inicio.
# 2. Click en "Crear tarea básica..."
# 3. Nombre: "Reporte Semanal Deportes"
# 4. Desencadenador: Semanalmente -> elige el día (ej. lunes) y la hora (ej. 8:00 AM)
# 5. Acción: "Iniciar un programa"
#    - Programa/script: ruta a python.exe (se obtiene con "where python" en cmd)
#    - Agregar argumentos: weekly_sports_report.py
#    - Iniciar en: la carpeta donde guardaste el script (ej. C:\\SportsReport)
# 6. Finalizar.
#
# Cada semana se generará/actualizará el archivo:
#    reports\\reporte_deportes.html
#
# Como el nombre del archivo es siempre el mismo, puedes dejarlo abierto
# como una pestaña fija en tu navegador y solo presionar F5 cada lunes
# para ver la versión más reciente.
#
# AGREGAR/QUITAR LIGAS:
#   Edita el diccionario SOURCES al inicio del archivo. Cada deporte tiene
#   un sub-diccionario {nombre_liga: url}. Puedes agregar nuevas URLs de
#   ligas de ESPN siguiendo el mismo formato.
# ---------------------------------------------------------------------------
