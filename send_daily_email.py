"""מייל חדשות יומי.

מריץ את סוכן CrewAI (run_news_agent מ-start.py), בונה מייל HTML בעברית (RTL)
ושולח אותו דרך Composio (Gmail). מיועד לריצה ב-Railway cron, אך ניתן להרצה גם מקומית:

    python send_daily_email.py

קונפיגורציה דרך משתני סביבה (.env מקומי / Railway service vars):
    COMPOSIO_API_KEY                 - מפתח Composio
    COMPOSIO_USER_ID                 - ברירת מחדל: default
    COMPOSIO_TOOLKIT_VERSION_GMAIL   - גרסת toolkit ל-Gmail (חובה ב-rc2)
    NEWS_CATEGORY                    - קטגוריית החדשות (ברירת מחדל: חדשות טכנולוגיה)
    EMAIL_RECIPIENT                  - כתובת הנמען
"""
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
load_dotenv()

from start import run_news_agent

# ─── קונפיגורציה ──────────────────────────────────────────────────────────────
CATEGORY = os.getenv("NEWS_CATEGORY", "חדשות טכנולוגיה")
RECIPIENT = os.getenv("EMAIL_RECIPIENT", "ariegoldman@gmail.com")
USER_ID = os.getenv("COMPOSIO_USER_ID", "default")
GMAIL_VER = os.getenv("COMPOSIO_TOOLKIT_VERSION_GMAIL", "20260515_00")


def build_html(category, items, today_str):
    """בונה גוף מייל HTML בעברית (RTL) עם כרטיס לכל כתבה."""
    rows = []
    for item in items:
        update = item.get("update", "")
        url = item.get("url", "")
        site = item.get("site", "")
        headline = (
            f'<a href="{url}" style="color:#1a73e8;text-decoration:none;">{update}</a>'
            if url else update
        )
        source = (
            f'<div style="font-size:12px;color:#888;margin-top:6px;">{site}</div>'
            if site else ""
        )
        rows.append(
            '<div style="background:#fff;border:1px solid #e5e5e5;border-radius:10px;'
            'padding:16px 18px;margin-bottom:12px;">'
            f'<div style="font-size:16px;line-height:1.5;color:#1a1a1a;">{headline}</div>'
            f'{source}'
            '</div>'
        )
    cards = "\n".join(rows) if rows else \
        '<div style="color:#888;">לא נמצאו עדכונים חדשים היום.</div>'

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f6;
             font-family:Arial,'Segoe UI',sans-serif;direction:rtl;">
  <div style="max-width:600px;margin:0 auto;padding:24px;">
    <h1 style="font-size:22px;color:#1a1a1a;margin:0 0 4px;">{category}</h1>
    <div style="font-size:13px;color:#888;margin-bottom:20px;">{today_str}</div>
    {cards}
    <div style="font-size:11px;color:#aaa;margin-top:24px;text-align:center;">
      נשלח אוטומטית · serper_test
    </div>
  </div>
</body>
</html>"""


def send_email(subject, html_body):
    """שולח מייל דרך Composio (Gmail). השולח נקבע לפי החשבון המחובר ל-user_id."""
    from composio import Composio

    client = Composio(toolkit_versions={"gmail": GMAIL_VER})
    result = client.tools.execute(
        slug="GMAIL_SEND_EMAIL",
        user_id=USER_ID,
        arguments={
            "recipient_email": RECIPIENT,
            "subject": subject,
            "body": html_body,
            "is_html": True,
        },
    )
    return result


def main():
    today_str = datetime.now().strftime("%d/%m/%Y")
    subject = f"{CATEGORY} לתאריך {today_str}"

    print(f"מריץ סוכן חדשות עבור: {CATEGORY}", flush=True)
    parsed, result_str = run_news_agent(CATEGORY)
    print(f"נמצאו {len(parsed)} כתבות.", flush=True)

    html_body = build_html(CATEGORY, parsed, today_str)

    print(f"שולח מייל אל {RECIPIENT} · נושא: {subject}", flush=True)
    result = send_email(subject, html_body)

    ok = isinstance(result, dict) and result.get("successful", True)
    if ok:
        print("✅ המייל נשלח בהצלחה.", flush=True)
    else:
        print(f"⚠️ תגובת Composio: {result}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
