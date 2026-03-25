import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from openai import OpenAI

EMAIL_LIST = os.environ.get('MENU_EMAIL_LIST', '').split(',')  # comma-separated
SMTP_SERVER = os.environ.get('MENU_SMTP_SERVER', 'smtp.example.com')
SMTP_PORT = int(os.environ.get('MENU_SMTP_PORT', '587'))
SMTP_USER = os.environ.get('MENU_SMTP_USER', 'user@example.com')
SMTP_PASS = os.environ.get('MENU_SMTP_PASS', 'password')

MENU_JSON_URL = 'https://www.sodexo.fi/ruokalistat/output/weekly_json/3207223'
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '').strip()

# TRANSLATION_MODEL = 'openrouter/free'
TRANSLATION_MODEL  = 'stepfun/step-3.5-flash:free'
MODEL_URL = 'https://openrouter.ai/api/v1'

TRANSLATION_PROMPT = (
    'You are a professional menu translator. '
    'Translate the provided English dish title into Simplified Chinese. '
    'Keep diet labels like (L,G), (M,G,V), numbers, and punctuation if present. '
    'Return only the translated Chinese text without explanation.'
)

DAY_NAMES = {
    'Maanantai': 'Monday',
    'Tiistai': 'Tuesday',
    'Keskiviikko': 'Wednesday',
    'Torstai': 'Thursday',
    'Perjantai': 'Friday',
    'Lauantai': 'Saturday',
    'Sunnuntai': 'Sunday',
}

translation_client = OpenAI(base_url=MODEL_URL, api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
translation_cache = {}


def translate_menu_bulk(titles_en):
    """
    Translate all menu titles in one API call.

    Args:
        titles_en: list of English food titles

    Returns:
        dict mapping eng_title -> zh_title
    """
    if not titles_en or translation_client is None:
        return {title: title for title in titles_en}

    # Filter out N/A values
    titles_to_translate = [t for t in set(titles_en) if t and t != 'N/A']
    if not titles_to_translate:
        return {title: title for title in titles_en}

    # Check cache first
    uncached = [t for t in titles_to_translate if t not in translation_cache]
    if not uncached:
        return {t: translation_cache.get(t, t) for t in titles_en}

    # Build bulk payload: one title per line
    bulk_text = '\n'.join(uncached)

    try:
        response = translation_client.chat.completions.create(
            model=TRANSLATION_MODEL,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a professional and culturally-aware restaurant menu translator.'
                        'I will provide a list of English dish titles (one per line).'
                        'Translate each title into **natural, common, and appealing Simplified Chinese restaurant menu names**.'
                        'Ensure the translation reflects authentic culinary terminology and avoids literal or awkward phrasing.'
                        'Crucially, preserve all dietary labels (e.g., (L,G), (M,G,V)), numbers, and punctuation exactly as they appear.'
                        'Maintain the original order, one translated title per line.'
                        'Return ONLY the translated Chinese titles, with nothing else.'
                    )
                },
                {'role': 'user', 'content': bulk_text},
            ],
            temperature=0,
        )
        translated_text = (response.choices[0].message.content or '').strip()
        translated_lines = translated_text.split('\n')
    except Exception:
        translated_lines = uncached  # Fallback to original

    # Map results back to cache
    for orig, trans in zip(uncached, translated_lines):
        translation_cache[orig] = trans.strip()

    # Return full mapping
    result = {}
    for title in titles_en:
        if title == 'N/A' or not title:
            result[title] = title
        else:
            result[title] = translation_cache.get(title, title)

    return result


def fetch_menu():
    resp = requests.get(MENU_JSON_URL, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    timeperiod = data.get('timeperiod', 'N/A')
    days = []
    for day_data in data.get('mealdates', []):
        date_fi = day_data.get('date', '')
        courses = day_data.get('courses', {})
        c1 = courses.get('1', {})
        c2 = courses.get('2', {})
        days.append({
            'date': DAY_NAMES.get(date_fi, date_fi),
            'c1_title': c1.get('title_en', 'N/A'),
            'c1_price': c1.get('price', 'N/A'),
            'c2_title': c2.get('title_en', 'N/A'),
            'c2_price': c2.get('price', 'N/A'),
        })
    return timeperiod, days


def translate_days(days):
    """
    Translate all dish titles in one bulk API call, then map back to days.
    """
    # Collect all English titles
    titles_en = []
    for day in days:
        if day['c1_title'] and day['c1_title'] != 'N/A':
            titles_en.append(day['c1_title'])
        if day['c2_title'] and day['c2_title'] != 'N/A':
            titles_en.append(day['c2_title'])

    # Translate all at once
    title_mapping = translate_menu_bulk(titles_en)

    # Apply translations to each day
    translated_days = []
    for day in days:
        translated_days.append({
            **day,
            'c1_title_zh': title_mapping.get(day['c1_title'], day['c1_title']),
            'c2_title_zh': title_mapping.get(day['c2_title'], day['c2_title']),
        })
    return translated_days


def format_menu(timeperiod, days):
    separator = '=' * 56

    # --- English Menu ---
    en_lines = [
        f'Nokia Linnanmaa Oulu — Weekly Menu  {timeperiod}',
        separator,
        '',
    ]
    for day in days:
        en_lines.append(f"  {day['date']}")
        en_lines.append(f"    1. FAVOURITES  : {day['c1_title']}")
        en_lines.append(f"                     {day['c1_price']}")
        en_lines.append(f"    2. FOOD MARKET : {day['c2_title']}")
        en_lines.append(f"                     {day['c2_price']}")
        en_lines.append('')
    en_lines.append(separator)
    en_section = '\n'.join(en_lines)

    # --- Chinese Menu ---
    zh_lines = [
        f'Nokia Linnanmaa Oulu — 周菜单  {timeperiod} (本菜单由模型step-3.5-flash提供AI翻译)',
        separator,
        '',
    ]
    for day in days:
        zh_lines.append(f"  {day['date']}")
        zh_lines.append(f"    1. 最爱菜肴    : {day['c1_title_zh']}")
        zh_lines.append(f"                     {day['c1_price']}")
        zh_lines.append(f"    2. 美食市场    : {day['c2_title_zh']}")
        zh_lines.append(f"                     {day['c2_price']}")
        zh_lines.append('')
    zh_lines.append(separator)
    zh_section = '\n'.join(zh_lines)

    # Combine both versions
    return en_section + '\n\n' + zh_section


def send_menu_email(timeperiod, days):
    subject = f'Nokia Linnanmaa Weekly Menu — {timeperiod}'
    body = format_menu(timeperiod, days)
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = ', '.join(EMAIL_LIST)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, EMAIL_LIST, msg.as_string())


if __name__ == '__main__':
    timeperiod, days = fetch_menu()
    days = translate_days(days)
    send_menu_email(timeperiod, days)
