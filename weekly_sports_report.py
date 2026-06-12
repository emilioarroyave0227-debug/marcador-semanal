"""
Weekly Sports News Report Generator
====================================

Scrapes ESPN pages for NFL (American Football), Volleyball, and Soccer
(Futbol), categorizes the headlines into Matches / Injuries / Transfers,
and generates a Markdown report.

Sources:
    - NFL:        https://www.espn.com/nfl/
    - Volleyball:  https://espndeportes.espn.com/voleibol/
    - Soccer:      https://www.espn.com.co/futbol/

Requirements:
    pip install requests beautifulsoup4 --break-system-packages

Usage:
    python weekly_sports_report.py

Optional weekly scheduling:
    See the bottom of this file for two ways to automate it
    (cron job or the `schedule` library).
"""

import os
import re
import datetime
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SOURCES = {
    "NFL (Football Americano)": "https://www.espn.com/nfl/",
    "Volleyball": "https://espndeportes.espn.com/voleibol/",
    "Soccer (Fútbol)": "https://www.espn.com.co/futbol/",
}

# Keywords used to classify each headline. Add/remove as needed.
INJURY_KEYWORDS = [
    "injury", "injured", "out for", "ruled out", "sidelined",
    "lesión", "lesionado", "baja por lesión", "se pierde",
    "dado de baja", "fuera de combate",
]

TRANSFER_KEYWORDS = [
    "transfer", "traded", "trade", "signs", "signing", "sign with",
    "agrees to", "deal", "free agent", "extension",
    "fichaje", "ficha por", "traspaso", "renovación", "renueva",
    "se va al", "nuevo equipo", "acuerdo",
]

# Where to save the reports
OUTPUT_DIR = "reports"

# Custom headers so ESPN doesn't immediately block the request
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

def fetch_page(url: str) -> BeautifulSoup | None:
    """Download a page and return a BeautifulSoup object, or None on error."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as exc:
        print(f"[WARN] Could not fetch {url}: {exc}")
        return None


def extract_headlines(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """
    Extract headline text + link from a parsed ESPN page.

    ESPN pages typically use <a> tags with classes like
    'contentItem__title' or similar for headlines/links inside
    article cards. We use a broad search and filter out junk.
    """
    headlines = []
    seen_titles = set()

    # Broad search: any <a> tag whose text looks like a real headline
    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True)
        href = a_tag["href"]

        # Skip empty, very short, or duplicate text
        if not text or len(text) < 15:
            continue
        if text in seen_titles:
            continue

        # Skip obvious navigation/menu links
        skip_words = ["Log In", "Sign Up", "Watch", "Listen",
                       "Schedule", "Standings", "Scores", "Tickets"]
        if any(word.lower() == text.lower() for word in skip_words):
            continue

        # Build absolute URL if needed
        if href.startswith("/"):
            href = base_url.rstrip("/") + href
        if not href.startswith("http"):
            continue

        seen_titles.add(text)
        headlines.append({"title": text, "link": href})

    return headlines


def classify_headline(title: str) -> str:
    """Return 'Injuries', 'Transfers', or 'Matches/General' based on keywords."""
    lower_title = title.lower()

    for kw in INJURY_KEYWORDS:
        if kw in lower_title:
            return "Injuries"

    for kw in TRANSFER_KEYWORDS:
        if kw in lower_title:
            return "Transfers"

    return "Matches / General News"


def get_base_url(url: str) -> str:
    """Return scheme + domain from a full URL, e.g. https://www.espn.com"""
    match = re.match(r"(https?://[^/]+)", url)
    return match.group(1) if match else url


# ---------------------------------------------------------------------------
# REPORT GENERATION
# ---------------------------------------------------------------------------

def build_report() -> str:
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=7)

    report_lines = [
        f"# Weekly Sports Report",
        f"**Period:** {week_start.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}",
        "",
    ]

    for sport_name, url in SOURCES.items():
        report_lines.append(f"## {sport_name}")
        report_lines.append(f"_Source: {url}_")
        report_lines.append("")

        soup = fetch_page(url)
        if soup is None:
            report_lines.append("> ⚠️ Could not retrieve data for this source.\n")
            continue

        base_url = get_base_url(url)
        headlines = extract_headlines(soup, base_url)

        if not headlines:
            report_lines.append("> No headlines found (page structure may have changed).\n")
            continue

        # Group by category
        categories = {"Matches / General News": [], "Injuries": [], "Transfers": []}
        for item in headlines:
            category = classify_headline(item["title"])
            categories[category].append(item)

        for category, items in categories.items():
            if not items:
                continue
            report_lines.append(f"### {category}")
            # Limit to top 10 per category to keep the report readable
            for item in items[:10]:
                report_lines.append(f"- [{item['title']}]({item['link']})")
            report_lines.append("")

    return "\n".join(report_lines)


def save_report(content: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"sports_report_{datetime.date.today().strftime('%Y-%m-%d')}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Report saved to: {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("Generating weekly sports report...")
    report = build_report()
    save_report(report)
    print("Done.")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# HOW TO AUTOMATE THIS WEEKLY
# ---------------------------------------------------------------------------
#
# OPTION 1 - Cron (Linux/Mac)
#   Run `crontab -e` and add a line like this to run every Monday at 8 AM:
#
#       0 8 * * 1 /usr/bin/python3 /path/to/weekly_sports_report.py
#
# OPTION 2 - Windows Task Scheduler
#   Create a new Basic Task -> Trigger: Weekly -> Action: Start a program
#   -> Program: python.exe -> Arguments: C:\path\to\weekly_sports_report.py
#
# OPTION 3 - The `schedule` library (run as a long-lived process)
#
#   pip install schedule --break-system-packages
#
#   import schedule
#   import time
#
#   schedule.every().monday.at("08:00").do(main)
#
#   while True:
#       schedule.run_pending()
#       time.sleep(60)
#
# ---------------------------------------------------------------------------
