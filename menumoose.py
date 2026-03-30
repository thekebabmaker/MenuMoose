#!/usr/bin/env python3
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import re
import ssl
import yaml
import httpx
from openai import OpenAI

# Load configuration from config.yml
with open('config.yml', 'r', encoding='utf-8') as f:
    CONFIG = yaml.safe_load(f)

# Email recipients from config file (visible and version-controlled)
EMAIL_LIST = CONFIG['recipients']
RECIPIENTS = [email.strip() for email in EMAIL_LIST if email and email.strip()]

# SMTP from config file
SMTP_SERVER = CONFIG['smtp']['server']
SMTP_PORT = CONFIG['smtp']['port']
SMTP_USER = os.environ.get('MENU_SMTP_USER')  # From GitHub Secrets
SMTP_PASS = os.environ.get('MENU_SMTP_PASS')  # From GitHub Secrets

# URLs and API config from config file
MENU_JSON_URL = CONFIG['menu_url']
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')  # From GitHub Secrets
TRANSLATION_MODEL = CONFIG['translation']['model']
MODEL_URL = CONFIG['translation']['api_base']
RESTAURANT_NAME = CONFIG['restaurant']['name']
RESTAURANT_URL = CONFIG['restaurant']['url']
MYSTERY_BOX = CONFIG['mystery_box']

TRANSLATION_PROMPT = (
    'You are a professional menu translator. '
    'Translate the provided English dish title into Simplified Chinese. '
    'Keep diet labels like (L,G), (M,G,V), numbers, and punctuation if present. '
    'Return only the translated Chinese text without explanation.'
)

DAY_NAMES = {
    'Maanantai': '📅 MONDAY · 周一',
    'Tiistai': '📅 TUESDAY · 周二',
    'Keskiviikko': '📅 WEDNESDAY · 周三',
    'Torstai': '📅 THURSDAY · 周四',
    'Perjantai': '📅 FRIDAY · 周五',
    'Lauantai': '📅 SATURDAY · 周六',
    'Sunnuntai': '📅 SUNDAY · 周日',
}

def _make_openai_client(base_url, api_key):
    """Create OpenAI client using system CA bundle.
    Works on both local machines (where Zscaler installs its CA into the system
    trust store) and GitHub Actions runners (standard Ubuntu CAs).
    httpx uses certifi by default which may not include corporate proxy CAs.
    """
    paths = ssl.get_default_verify_paths()
    system_ca = paths.cafile or paths.openssl_cafile
    if system_ca:
        print(f'  [openai] Using CA bundle: {system_ca}', flush=True)
        http_client = httpx.Client(verify=system_ca)
        return OpenAI(base_url=base_url, api_key=api_key, http_client=http_client)
    else:
        print('  [openai] No system CA found, using certifi default', flush=True)
        return OpenAI(base_url=base_url, api_key=api_key)


translation_client = _make_openai_client(MODEL_URL, OPENAI_API_KEY) if OPENAI_API_KEY else None
translation_cache = {}


def _clean_translation_lines(raw_text):
    """Normalize model output lines so minor format drift won't break mapping."""
    text = (raw_text or '').strip()
    if text.startswith('```'):
        text = text.strip('`')
        text = text.replace('text', '', 1).replace('markdown', '', 1).replace('json', '', 1).strip()

    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Remove common list prefixes like "1. ", "- ", "* " etc.
        line = re.sub(r'^\s*(?:[-*•]|\d+[\.)])\s*', '', line)
        if line:
            lines.append(line)
    return lines


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

    # Keep original order while deduplicating, so translations map correctly.
    seen = set()
    titles_to_translate = []
    for t in titles_en:
        if not t or t == 'N/A':
            continue
        if t in seen:
            continue
        seen.add(t)
        titles_to_translate.append(t)
    if not titles_to_translate:
        return {title: title for title in titles_en}

    # Check cache first
    uncached = [t for t in titles_to_translate if t not in translation_cache]
    if not uncached:
        return {t: translation_cache.get(t, t) for t in titles_en}

    # Build bulk payload: one title per line
    bulk_text = '\n'.join(uncached)

    print(f'  [translate] Calling {MODEL_URL} model={TRANSLATION_MODEL}, {len(uncached)} titles...', flush=True)
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
        translated_text = response.choices[0].message.content or ''
        print(f'  [translate] API response received ({len(translated_text)} chars)', flush=True)
        translated_lines = _clean_translation_lines(translated_text)

        # Keep partial success: truncate extras and pad missing with originals.
        if len(translated_lines) > len(uncached):
            translated_lines = translated_lines[:len(uncached)]
        elif len(translated_lines) < len(uncached):
            translated_lines.extend(uncached[len(translated_lines):])
    except Exception as e:
        print(f'  [translate] API call failed: {e}', flush=True)
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
    print(f'  [fetch_menu] GET {MENU_JSON_URL}', flush=True)
    resp = requests.get(MENU_JSON_URL, timeout=15)
    resp.raise_for_status()
    print(f'  [fetch_menu] HTTP {resp.status_code}, {len(resp.content)} bytes', flush=True)
    data = resp.json()

    def split_items(title_en):
        """Split a course title into individual dish names (separated by ' / ')."""
        if not title_en or title_en.strip() == 'N/A':
            return []
        return [t.strip() for t in title_en.split('/') if t.strip()]

    timeperiod = data.get('timeperiod', 'N/A')
    days = []
    for day_data in data.get('mealdates', []):
        date_fi = day_data.get('date', '')
        courses = day_data.get('courses', {})
        c1 = courses.get('1', {})
        c2 = courses.get('2', {})
        days.append({
            'date': DAY_NAMES.get(date_fi, date_fi),
            'c1_items': split_items(c1.get('title_en', '')),
            'c1_price': c1.get('price', 'N/A'),
            'c2_items': split_items(c2.get('title_en', '')),
            'c2_price': c2.get('price', 'N/A'),
        })
    return timeperiod, days


def translate_days(days):
    """
    Translate all dish titles in one bulk API call, then map back to days.
    """
    # Collect all individual English titles (c1 and c2 are now lists)
    titles_en = []
    for day in days:
        titles_en.extend(day['c1_items'])
        titles_en.extend(day['c2_items'])

    # Translate all at once
    title_mapping = translate_menu_bulk(titles_en)

    # Apply translations to each day
    translated_days = []
    for day in days:
        translated_days.append({
            **day,
            'c1_items_zh': [title_mapping.get(t, t) for t in day['c1_items']],
            'c2_items_zh': [title_mapping.get(t, t) for t in day['c2_items']],
        })
    return translated_days


def format_menu(timeperiod, days):
    border = '━' * 30
    thin   = '─' * 50

    lines = [
        f'┏{border}┓',
        f'   NOKIA LINNANMAA OULU  |  Weekly Menu 每周菜单',
        f'   {timeperiod}',
        f'┗{border}┛',
        '',
        '饮食标签 | DIET LABELS',
        'G: Gluten free 无麸质  L: Lactose free 无乳糖  M: Milk-free 无奶制品  VL: Low lactose 低乳糖',
        '',
    ]

    for day in days:
        lines.append(day['date'])
        lines.append(thin)

        # FAVOURITES
        lines.append(f'🌟 FAVOURITES  |  {day["c1_price"]}')
        for en, zh in zip(day['c1_items'], day['c1_items_zh']):
            failed = (en == zh)
            lines.append(f'   • {en}')
            lines.append(f'     {zh}{"（翻译失败）" if failed else ""}')

        lines.append('')

        # FOOD MARKET
        lines.append(f'🛒 FOOD MARKET  |  {day["c2_price"]}')
        for en, zh in zip(day['c2_items'], day['c2_items_zh']):
            failed = (en == zh)
            lines.append(f'   • {en}')
            lines.append(f'     {zh}{"（翻译失败）" if failed else ""}')

        lines.append('')
        lines.append(thin)
        lines.append('')

    lines += [
        '💡 温馨提示 | SERVICE INFO',
        f'• 剩菜盲盒 (Leftover Box): 13:00 - 13:10 | 7,70€/kg',
        f'• 菜单来源: sodexo.fi (Nokia Linnanmaa)',
        f'• Powered by: MenuMoose🦌 & {TRANSLATION_MODEL} ',
        '',
        'Bon appétit! 祝您用餐愉快！',
    ]
    return '\n'.join(lines)


def send_menu_email(timeperiod, days):
    subject = f'🍽️ Nokia Linnanmaa Oulu Weekly Menu — {timeperiod}'
    body = format_menu(timeperiod, days)
    if not RECIPIENTS:
        raise ValueError('No recipients configured in config.yml (recipients).')

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    # Keep recipients private: do not expose subscriber addresses in email headers.
    msg['To'] = 'undisclosed-recipients:;'
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    print(f'  [smtp] Connecting to {SMTP_SERVER}:{SMTP_PORT}...', flush=True)
    paths = ssl.get_default_verify_paths()
    system_ca = paths.cafile or paths.openssl_cafile
    ssl_ctx = ssl.create_default_context(cafile=system_ca)
    if SMTP_PORT == 465:
        # Port 465: direct SSL (SMTPS), no STARTTLS needed
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30, context=ssl_ctx) as server:
            print(f'  [smtp] Logging in as {SMTP_USER}...', flush=True)
            server.login(SMTP_USER, SMTP_PASS)
            print(f'  [smtp] Sending to {len(RECIPIENTS)} recipient(s)...', flush=True)
            server.sendmail(SMTP_USER, RECIPIENTS, msg.as_string())
    else:
        # Port 587: STARTTLS upgrade with system CA (handles Zscaler MITM cert)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            print('  [smtp] Starting TLS...', flush=True)
            server.starttls(context=ssl_ctx)
            print(f'  [smtp] Logging in as {SMTP_USER}...', flush=True)
            server.login(SMTP_USER, SMTP_PASS)
            print(f'  [smtp] Sending to {len(RECIPIENTS)} recipient(s)...', flush=True)
            server.sendmail(SMTP_USER, RECIPIENTS, msg.as_string())


if __name__ == '__main__':
    print('[1/4] Fetching menu...', flush=True)
    timeperiod, days = fetch_menu()
    print(f'[2/4] Menu fetched: {timeperiod}, {len(days)} days', flush=True)

    print('[3/4] Translating menu...', flush=True)
    days = translate_days(days)
    print('[4/4] Translation done. Sending email...', flush=True)

    send_menu_email(timeperiod, days)
    print('Done. Email sent successfully.', flush=True)
