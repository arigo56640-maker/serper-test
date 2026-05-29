import sys
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
load_dotenv()

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "search_history.json")

SITES_BY_TOPIC = {
    "חדשות טכנולוגיה":  ["geektime.co.il", "calcalist.co.il", "techtime.co.il", "themarker.com", "ynet.co.il", "walla.co.il", "mako.co.il"],
    "חדשות ביטחוניות": ["ynet.co.il", "mako.co.il", "walla.co.il", "maariv.co.il", "israelhayom.co.il", "kan.org.il", "n12.co.il"],
    "חדשות ספורט":     ["sport5.co.il", "one.co.il", "mako.co.il", "ynet.co.il", "walla.co.il", "n12.co.il", "kan.org.il"],
    "חדשות תרבות":     ["ynet.co.il", "mako.co.il", "walla.co.il", "haaretz.co.il", "maariv.co.il", "kan.org.il", "n12.co.il"],
    "חדשות כלכלה":     ["calcalist.co.il", "globes.co.il", "themarker.com", "ynet.co.il", "walla.co.il", "mako.co.il", "bizportal.co.il"],
    "חדשות פוליטיקה":  ["ynet.co.il", "mako.co.il", "haaretz.co.il", "maariv.co.il", "israelhayom.co.il", "kan.org.il", "n12.co.il"],
}


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def get_sites_for_topic(topic):
    return SITES_BY_TOPIC.get(topic, list(SITES_BY_TOPIC.values())[0])[:5]


def get_seen_articles_by_site(history, topic):
    """Returns {site: [update, ...]} for all previously saved articles for this topic."""
    seen = {}
    for item in history:
        if item.get('category') == topic:
            site = item['site']
            seen.setdefault(site, []).append(item['update'])
    return seen


def is_duplicate_article(history, site, update):
    return any(i.get('site') == site and i.get('update') == update for i in history)


def save_to_history(topic, results):
    history = load_history()
    now = datetime.now().isoformat()
    for item in results:
        history.append({
            "date": now,
            "category": topic,
            "site": item["site"],
            "url": item.get("url", ""),
            "update": item["update"]
        })
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ─── קבלת נושא ───────────────────────────────────────────────────────────────
topic = sys.argv[1] if len(sys.argv) > 1 else "חדשות טכנולוגיה"

history = load_history()
sites_to_search = get_sites_for_topic(topic)
seen_by_site = get_seen_articles_by_site(history, topic)

print(f"נושא: {topic}", flush=True)
print(f"אתרים: {', '.join(sites_to_search)}", flush=True)

search_tool = SerperDevTool()

# ─── בניית רשימת כתבות שיש להימנע מהן ───────────────────────────────────────
avoid_section = ""
if seen_by_site:
    lines = []
    for site in sites_to_search:
        if site in seen_by_site:
            quoted = ", ".join(f'"{h}"' for h in seen_by_site[site])
            lines.append(f"- {site}: {quoted}")
    if lines:
        avoid_section = (
            "\n\nכתבות שכבר הוצגו — אין לחזור עליהן:\n" + "\n".join(lines)
        )

# ─── סוכן חדשות ──────────────────────────────────────────────────────────────
news_agent = Agent(
    role='עיתונאי ישראלי',
    goal=f'למצוא 5 עדכוני {topic} מהאתרים הישראליים שסופקו',
    backstory=(
        'אתה עיתונאי ישראלי המחפש חדשות אך ורק מהאתרים שסופקו. '
        'הכותרת עצמה חייבת להיות תוכן החדשה בלבד — אין לציין בה מי מדווח, מאיזה אתר היא נלקחה, או כל ציון מקור אחר.'
    ),
    verbose=False,
    allow_delegation=False,
    tools=[search_tool]
)

sites_list = '\n'.join(f'- {s}' for s in sites_to_search)
news_task = Task(
    description=(
        f'חפש {topic} עדכניות אך ורק מהאתרים הבאים:\n{sites_list}\n\n'
        'לכל חיפוש הוסף site:שם_האתר לשאילתה.\n'
        'מצא 5 עדכונים עדכניים ושונים — כתבה אחת בלבד מכל אתר.\n\n'
        'פלט חובה — בדיוק 5 שורות, כל שורה בפורמט:\n'
        'SITE: שם_הדומיין | URL: קישור_מלא_לכתבה | UPDATE: תיאור העדכון במשפט אחד בעברית\n\n'
        'חשוב: בשדה UPDATE כתוב את תוכן החדשה בלבד. אל תציין בתוכו שם אתר, ואל תכתוב ביטויים כמו "מדווח", "מפרסם", "לפי" וכו\'.'
        + avoid_section
    ),
    expected_output=(
        'בדיוק 5 שורות בפורמט:\n'
        'SITE: ynet.co.il | URL: https://www.ynet.co.il/... | UPDATE: ...\n'
        'וכן הלאה'
    ),
    agent=news_agent
)

crew = Crew(
    agents=[news_agent],
    tasks=[news_task],
    process=Process.sequential
)

result = crew.kickoff()
result_str = str(result)

# ─── פירוס ───────────────────────────────────────────────────────────────────
parsed_raw = []
for line in result_str.split('\n'):
    m = re.search(r'SITE[:\s]+([^\|]+)\|.*?URL[:\s]+(https?://\S+)\s*\|\s*UPDATE[:\s]+(.*)', line, re.IGNORECASE)
    if m:
        site = m.group(1).strip()
        url  = m.group(2).strip()
        update = m.group(3).strip()
        if site and update:
            parsed_raw.append({"site": site, "url": url, "update": update})
    else:
        m2 = re.search(r'SITE[:\s]+([^\|]+)\|\s*UPDATE[:\s]+(.*)', line, re.IGNORECASE)
        if m2:
            site = m2.group(1).strip()
            update = m2.group(2).strip()
            if site and update:
                parsed_raw.append({"site": site, "url": "", "update": update})

# ─── ניקוי כפילויות: כתבה אחת לאתר לכל הרצה, ואין חזרה על כתבה שהופיעה בעבר ─
seen_sites_this_run = set()
parsed = []
for item in parsed_raw:
    site = item["site"]
    if site in seen_sites_this_run:
        continue
    if is_duplicate_article(history, site, item["update"]):
        continue
    seen_sites_this_run.add(site)
    parsed.append(item)

if parsed:
    save_to_history(topic, parsed)

print("\n" + "=" * 50, flush=True)
print(f"{topic}:", flush=True)
print("=" * 50, flush=True)

if parsed:
    for item in parsed:
        url_part = f"|{item['url']}" if item.get('url') else ""
        print(f"[{item['site']}{url_part}] {item['update']}", flush=True)
else:
    print(result_str, flush=True)
