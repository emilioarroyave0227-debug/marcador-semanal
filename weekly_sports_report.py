\"""
Reporte Semanal de Deportes (HTML) - v4
=========================================

CAMBIO IMPORTANTE respecto a versiones anteriores:
ESPN carga sus páginas con JavaScript, así que descargar el HTML
"crudo" no muestra las noticias (por eso antes salía vacío).

Esta versión usa las APIs JSON públicas que ESPN usa internamente
para cargar noticias y resultados (site.api.espn.com). Son mucho
más confiables.

Incluye:
    Fútbol:
        - Mundial 2026
        - Premier League
        - La Liga
        - Champions League
        - Liga BetPlay (Colombia)

    NFL (Football Americano):
        - NFL
        - NCAA Football (Universitario)

    NBA / Baloncesto:
        - NBA

    Voleibol:
        - General (ESPN Deportes) -- mediante scraping HTML
          (ESPN no siempre tiene API pública de voleibol, así que
          esta sección puede salir vacía si la página no trae
          contenido estático. Si pasa eso, te lo aviso al final.)

Para cada liga con API se muestran:
    1. Noticias de los últimos N días, separadas en:
       Lesiones / Transferencias / Análisis y Opiniones / General
    2. Jugadores destacados (líderes estadísticos) de los partidos
       recientes.

Requisitos (instalar una sola vez):
    pip install requests beautifulsoup4

Uso:
    python weekly_sports_report.py
"""

import os
import datetime
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------------------

API_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Estructura: grupo_deporte -> lista de (nombre_liga, sport_path, league_path)
SPORTS = {
    "Fútbol ⚽": [
        ("Mundial 2026", "soccer", "fifa.world"),
        ("Premier League", "soccer", "eng.1"),
        ("La Liga", "soccer", "esp.1"),
        ("Champions League", "soccer", "uefa.champions"),
        ("Liga BetPlay (Colombia)", "soccer", "col.1"),
    ],
    "NFL (Football Americano) 🏈": [
        ("NFL", "football", "nfl"),
        ("NCAA Football (Universitario)", "football", "college-football"),
    ],
    "NBA / Baloncesto 🏀": [
        ("NBA", "basketball", "nba"),
    ],
}

# Voleibol no siempre tiene API pública en ESPN -> se intenta scraping HTML
VOLLEYBALL_SOURCES = {
    "General (ESPN Deportes)": "https://espndeportes.espn.com/voleibol/",
}

# Palabras clave para clasificar noticias
INJURY_KEYWORDS = [
    "injury", "injured", "out for", "ruled out", "sidelined", "hurt",
    "lesión", "lesion", "lesionado", "baja por lesión", "se pierde",
    "dado de baja", "fuera de combate", "molestia",
]

TRANSFER_KEYWORDS = [
    "transfer", "traded", "trade", "signs", "signing", "sign with",
    "agrees to", "deal", "free agent", "extension", "waived", "released",
    "fichaje", "ficha por", "traspaso", "renovación", "renovacion",
    "renueva", "se va al", "nuevo equipo", "acuerdo", "contrato",
]

# Tipos de artículo de ESPN que consideramos "análisis / opinión"
OPINION_TYPES = [
    "Analysis", "Commentary", "Column", "PowerRankings", "Opinion",
    "Notebook", "Insider",
]

OUTPUT_DIR = "reports"
HTML_FILENAME = "index.html"  # nombre requerido por GitHub Pages para la página principal

# Branding del sitio
SITE_NAME = "Marcador Semanal"
SITE_AUTHOR = "Emilio"

DAYS_BACK = 8           # cuántos días atrás incluir en noticias
MAX_NEWS_PER_CATEGORY = 6
MAX_LEADERS = 6
TOP_N_RELEVANT = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def fetch_json(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"    [AVISO] No se pudo obtener {url}: {exc}")
        return None


def parse_date(date_str: str):
    if not date_str:
        return None
    try:
        # Formato típico de ESPN: 2026-06-09T20:30Z
        return datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def classify_news(title: str, description: str, article_type: str) -> str:
    text = f"{title} {description}".lower()

    for kw in INJURY_KEYWORDS:
        if kw in text:
            return "Lesiones"

    for kw in TRANSFER_KEYWORDS:
        if kw in text:
            return "Transferencias"

    if article_type in OPINION_TYPES:
        return "Análisis y Opiniones"

    return "General"


# ---------------------------------------------------------------------------
# NOTICIAS (API)
# ---------------------------------------------------------------------------

def get_news(sport_path: str, league_path: str) -> dict:
    """Devuelve noticias recientes categorizadas para una liga."""
    url = f"{API_BASE}/{sport_path}/{league_path}/news"
    data = fetch_json(url)

    categories = {
        "Lesiones": [],
        "Transferencias": [],
        "Análisis y Opiniones": [],
        "General": [],
    }

    if not data:
        return {"error": True, "categories": categories}

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DAYS_BACK)

    for article in data.get("articles", []):
        title = article.get("headline", "").strip()
        if not title:
            continue

        description = article.get("description", "") or ""
        link = article.get("links", {}).get("web", {}).get("href", "")
        article_type = article.get("type", "")
        published = parse_date(article.get("published", ""))

        if published and published < cutoff:
            continue

        category = classify_news(title, description, article_type)
        categories[category].append({
            "title": title,
            "description": description,
            "link": link,
            "published": published,
        })

    return {"error": False, "categories": categories}


# ---------------------------------------------------------------------------
# JUGADORES DESTACADOS / ESTADISTICAS (API scoreboard)
# ---------------------------------------------------------------------------

def get_leaders(sport_path: str, league_path: str) -> list:
    """Devuelve líderes estadísticos de los partidos recientes (scoreboard)."""
    url = f"{API_BASE}/{sport_path}/{league_path}/scoreboard"
    data = fetch_json(url)

    if not data:
        return []

    results = []
    for event in data.get("events", []):
        competitions = event.get("competitions", [])
        if not competitions:
            continue
        comp = competitions[0]

        competitors = comp.get("competitors", [])
        team_names = [c.get("team", {}).get("displayName", "?") for c in competitors]
        matchup = " vs ".join(team_names) if team_names else event.get("name", "")

        for leader_group in comp.get("leaders", []) or []:
            cat_name = leader_group.get("displayName", "")
            for leader in (leader_group.get("leaders") or [])[:1]:
                athlete = leader.get("athlete", {}).get("displayName", "")
                value = leader.get("displayValue", "")
                if not athlete or not value:
                    continue
                results.append({
                    "matchup": matchup,
                    "category": cat_name,
                    "athlete": athlete,
                    "value": value,
                })

    return results[:MAX_LEADERS * 3]  # margen, luego se recorta por liga


# ---------------------------------------------------------------------------
# VOLEIBOL (scraping HTML, mejor esfuerzo)
# ---------------------------------------------------------------------------

def get_volleyball_headlines(url: str) -> list:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        print(f"    [AVISO] No se pudo obtener {url}: {exc}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True)
        href = a_tag["href"]

        if not text or len(text) < 12:
            continue
        if text in seen:
            continue
        if not href.startswith("http"):
            if href.startswith("/"):
                href = "https://espndeportes.espn.com" + href
            else:
                continue

        seen.add(text)
        headlines.append({"title": text, "link": href})

    return headlines[:15]


# ---------------------------------------------------------------------------
# GENERACION DE HTML
# ---------------------------------------------------------------------------

HTML_HEAD_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{site_name}</title>
<style>
    :root {{
        --bg: #0f1115;
        --card: #1a1d24;
        --accent: #ff5a36;
        --accent2: #36c2ff;
        --accent3: #7cf29c;
        --text: #e8e8e8;
        --muted: #9aa0aa;
        --border: #2a2e37;
    }}
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        font-family: 'Segoe UI', Arial, sans-serif;
        background: var(--bg);
        color: var(--text);
        line-height: 1.5;
    }}
    header {{
        background: linear-gradient(90deg, var(--accent), var(--accent2));
        padding: 30px 20px;
        text-align: center;
        position: relative;
    }}
    .brand {{
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: rgba(255,255,255,0.85);
        margin-bottom: 6px;
    }}
    header h1 {{ margin: 0; font-size: 28px; color: #fff; }}
    header p {{ margin: 6px 0 0; color: rgba(255,255,255,0.9); font-size: 14px; }}
    .container {{ max-width: 950px; margin: 0 auto; padding: 20px; }}

    .summary {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 30px;
    }}
    .summary h2 {{ margin-top: 0; color: var(--accent); font-size: 20px; }}
    .summary-item {{ padding: 8px 0; border-bottom: 1px solid var(--border); }}
    .summary-item:last-child {{ border-bottom: none; }}
    .summary-item a {{ color: var(--text); text-decoration: none; font-weight: 500; }}
    .summary-item a:hover {{ color: var(--accent2); }}

    .tag {{
        display: inline-block;
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 12px;
        margin-right: 6px;
        font-weight: bold;
        text-transform: uppercase;
        white-space: nowrap;
    }}
    .tag-sport {{ background: var(--accent2); color: #00222e; }}
    .tag-cat {{ background: var(--accent); color: #2e0a00; }}
    .tag-league {{ background: #3a3f4b; color: var(--text); }}
    .tag-stat {{ background: var(--accent3); color: #003311; }}

    .group-title {{
        font-size: 26px;
        margin: 40px 0 10px;
        border-bottom: 3px solid var(--accent2);
        padding-bottom: 6px;
    }}
    .league-section {{ margin-bottom: 30px; }}
    .league-section h3 {{
        font-size: 19px;
        margin-bottom: 4px;
        color: #fff;
    }}
    .failed-note {{ font-size: 12px; color: var(--muted); margin: 4px 0; }}

    .category-block {{ margin-top: 14px; }}
    .category-block h4 {{
        font-size: 14px;
        color: var(--accent2);
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    ul.news-list {{ list-style: none; padding: 0; margin: 0; }}
    ul.news-list li {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
    }}
    ul.news-list a {{ color: var(--text); text-decoration: none; font-weight: 500; }}
    ul.news-list a:hover {{ color: var(--accent2); text-decoration: underline; }}
    .news-desc {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}

    .leaders-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
        margin-top: 6px;
    }}
    .leaders-table th, .leaders-table td {{
        text-align: left;
        padding: 6px 10px;
        border-bottom: 1px solid var(--border);
    }}
    .leaders-table th {{ color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; }}

    .empty-msg {{ color: var(--muted); font-style: italic; }}
    footer {{
        text-align: center;
        color: var(--muted);
        font-size: 12px;
        padding: 25px 20px;
        border-top: 1px solid var(--border);
        margin-top: 20px;
    }}
    footer .watermark {{
        font-size: 13px;
        color: var(--text);
        font-weight: 700;
        letter-spacing: 1px;
        margin-bottom: 4px;
    }}
    footer .watermark span {{ color: var(--accent2); }}
</style>
</head>
<body>
"""

HTML_FOOT = """
</body>
</html>
"""


def render_news_categories(categories: dict) -> list:
    parts = []
    order = ["Lesiones", "Transferencias", "Análisis y Opiniones", "General"]
    any_news = False

    for cat_name in order:
        items = categories.get(cat_name, [])
        if not items:
            continue
        any_news = True
        parts.append(f'<div class="category-block"><h4>{cat_name}</h4>')
        parts.append('<ul class="news-list">')
        for item in items[:MAX_NEWS_PER_CATEGORY]:
            desc_html = f'<div class="news-desc">{item["description"]}</div>' if item.get("description") else ""
            parts.append(
                f'<li><a href="{item["link"]}" target="_blank">{item["title"]}</a>{desc_html}</li>'
            )
        parts.append("</ul></div>")

    if not any_news:
        parts.append('<p class="empty-msg">No se encontraron noticias recientes para esta liga.</p>')

    return parts


def render_leaders(leaders: list) -> list:
    parts = []
    if not leaders:
        return parts

    # Limitar y deduplicar por (categoria, jugador)
    seen = set()
    rows = []
    for l in leaders:
        key = (l["category"], l["athlete"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(l)
        if len(rows) >= MAX_LEADERS:
            break

    if not rows:
        return parts

    parts.append('<div class="category-block"><h4>📊 Jugadores destacados (últimos partidos)</h4>')
    parts.append('<table class="leaders-table"><tr><th>Partido</th><th>Categoría</th><th>Jugador</th><th>Valor</th></tr>')
    for r in rows:
        parts.append(
            f'<tr><td>{r["matchup"]}</td><td>{r["category"]}</td>'
            f'<td>{r["athlete"]}</td><td><span class="tag tag-stat">{r["value"]}</span></td></tr>'
        )
    parts.append("</table></div>")
    return parts


def build_html(news_data: dict, leaders_data: dict, volleyball_data: dict) -> str:
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=7)

    parts = [HTML_HEAD_TEMPLATE.format(site_name=SITE_NAME)]
    parts.append(f"""
<header>
    <div class="brand">{SITE_NAME}</div>
    <h1>📰 Reporte Semanal de Deportes</h1>
    <p>Del {week_start.strftime('%d/%m/%Y')} al {today.strftime('%d/%m/%Y')}</p>
</header>
<div class="container">
""")

    # --- Resumen / Lo más relevante ---
    parts.append('<div class="summary"><h2>⭐ Lo más relevante de la semana</h2>')
    any_relevant = False
    for group_name, leagues in SPORTS.items():
        for league_name, sport_path, league_path in leagues:
            data = news_data.get((group_name, league_name), {})
            categories = data.get("categories", {})
            for cat_name in ["Lesiones", "Transferencias", "Análisis y Opiniones"]:
                for item in categories.get(cat_name, [])[:2]:
                    any_relevant = True
                    parts.append(f"""
<div class="summary-item">
    <span class="tag tag-sport">{group_name}</span>
    <span class="tag tag-league">{league_name}</span>
    <span class="tag tag-cat">{cat_name}</span>
    <a href="{item['link']}" target="_blank">{item['title']}</a>
</div>
""")
    if not any_relevant:
        parts.append('<p class="empty-msg">No se encontraron noticias destacadas esta semana.</p>')
    parts.append("</div>")

    # --- Secciones por grupo de deporte ---
    for group_name, leagues in SPORTS.items():
        parts.append(f'<h2 class="group-title">{group_name}</h2>')

        for league_name, sport_path, league_path in leagues:
            data = news_data.get((group_name, league_name), {})
            leaders = leaders_data.get((group_name, league_name), [])

            parts.append(f'<div class="league-section"><h3>{league_name}</h3>')

            if data.get("error"):
                parts.append('<p class="failed-note">⚠️ No se pudo obtener información de esta liga.</p>')
                parts.append("</div>")
                continue

            parts.extend(render_leaders(leaders))
            parts.extend(render_news_categories(data.get("categories", {})))

            parts.append("</div>")

    # --- Voleibol ---
    parts.append('<h2 class="group-title">Voleibol 🏐</h2>')
    for source_name, items in volleyball_data.items():
        parts.append(f'<div class="league-section"><h3>{source_name}</h3>')
        if not items:
            parts.append(
                '<p class="failed-note">⚠️ No se encontraron noticias automáticamente. '
                'ESPN suele mostrar el voleibol con contenido cargado por JavaScript, '
                'así que esta sección puede salir vacía. '
                'Si necesitas la VNL específicamente, dímelo y agrego la fuente '
                'oficial de la FIVB como fuente alternativa.</p>'
            )
        else:
            parts.append('<ul class="news-list">')
            for item in items[:10]:
                parts.append(f'<li><a href="{item["link"]}" target="_blank">{item["title"]}</a></li>')
            parts.append("</ul>")
        parts.append("</div>")

    parts.append("</div>")  # cierre container
    parts.append(f"""
<footer>
    <div class="watermark">{SITE_NAME} <span>•</span> by {SITE_AUTHOR}</div>
    Generado automáticamente el {today.strftime('%d/%m/%Y a las %H:%M')}.
</footer>
""")
    parts.append(HTML_FOOT)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("Generando reporte semanal de deportes...\n")

    news_data = {}
    leaders_data = {}

    for group_name, leagues in SPORTS.items():
        print(f"== {group_name} ==")
        for league_name, sport_path, league_path in leagues:
            print(f"  - {league_name}: descargando noticias...")
            news_data[(group_name, league_name)] = get_news(sport_path, league_path)

            print(f"  - {league_name}: descargando líderes/estadísticas...")
            leaders_data[(group_name, league_name)] = get_leaders(sport_path, league_path)

    print("\n== Voleibol ==")
    volleyball_data = {}
    for source_name, url in VOLLEYBALL_SOURCES.items():
        print(f"  - {source_name}: descargando...")
        volleyball_data[source_name] = get_volleyball_headlines(url)

    html_content = build_html(news_data, leaders_data, volleyball_data)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, HTML_FILENAME)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\nReporte guardado en: {filepath}")
    print("Listo. Abre ese archivo .html en tu navegador para verlo.")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# COMO PUBLICARLO EN INTERNET (GitHub Pages + GitHub Actions)
# ---------------------------------------------------------------------------
#
# Este script genera "reports/index.html". Si lo subes a un repositorio de
# GitHub y activas GitHub Pages apuntando a la carpeta "reports", obtienes
# un link público como:
#
#     https://TU_USUARIO.github.io/marcador-semanal/
#
# Y con GitHub Actions, este script se ejecuta SOLO, automáticamente,
# cada semana, sin que tu PC necesite estar prendido.
#
# Sigue la guía completa que te dio Claude paso a paso (creación del
# repositorio, archivo de workflow .github/workflows/weekly.yml, y
# activación de GitHub Pages).
# ---------------------------------------------------------------------------
#
# AUTOMATIZACION LOCAL (alternativa con Windows Task Scheduler):
#   Ver instrucciones en conversaciones anteriores. La versión de
#   GitHub Actions es preferible porque no depende de que tu PC
#   esté encendido.
#
# AGREGAR/QUITAR LIGAS:
#   Edita el diccionario SPORTS al inicio del archivo. Cada entrada es
#   (nombre_a_mostrar, sport_path, league_path) según la nomenclatura
#   de ESPN (ej. soccer/eng.1, basketball/nba, football/nfl).
# ---------------------------------------------------------------------------
