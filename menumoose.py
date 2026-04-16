#!/usr/bin/env python3
import argparse
import requests
import html as html_lib
import os
import re
import ssl
import time
import yaml
import httpx
from itertools import zip_longest
from openai import OpenAI
import resend

# Load configuration from config.yml
with open('config.yml', 'r', encoding='utf-8') as f:
    CONFIG = yaml.safe_load(f)

# Email recipients from config file (visible and version-controlled)
EMAIL_LIST = CONFIG['recipients']
RECIPIENTS = [email.strip() for email in EMAIL_LIST if email and email.strip()]
EMAIL_LIST_TEST = CONFIG.get('recipients_test', [])
RECIPIENTS_TEST = [email.strip() for email in EMAIL_LIST_TEST if email and email.strip()]

# Resend API from environment
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
RESEND_FROM_EMAIL = CONFIG.get('resend_from_email', 'noreply@panda-tech.top')

# URLs and API config from config file
MENU_JSON_URL = CONFIG['menu_url']
# OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')  # From GitHub Secrets
OPENAI_API_KEY = os.environ.get('ALIYUN_API_KEY')  # From GitHub Secrets
# MODEL_URL = CONFIG['translation']['api_base']
MODEL_URL = CONFIG['translation']['aliyun_api_base']
TRANSLATION_MODEL = CONFIG['translation']['model']
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
                        'You are a professional and culturally-aware Finnish-to-Chinese culinary translator.'
                        'I will provide a list of Finnish dish titles (one per line).'
                        'Translate each into **appealing, professional Simplified Chinese menu names** that balance appetite appeal with Nordic elegance.'
                        'Guidelines: '
                        '1. Use standard Chinese Western-cuisine terminology (e.g., use "香煎" for paistettu, "慢炖" for haudutettu). '
                        '2. Be precise with Finnish ingredients: translate "Kirjolohi" as 虹鳟, "Riista" as 野味/鹿肉 based on context. '
                        '3. **Strictly preserve** all dietary labels like (L, G), (M, G, V), numbers, and original punctuation. '
                        '4. Avoid robotic literal translation; for example, "Lohikeitto" should be "芬兰传统奶油三文鱼浓汤" rather than just "三文鱼汤". '
                        '5. Maintain the original order, one translated title per line. '
                        'Return ONLY the translated Chinese titles, with no introductory or concluding text.'
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


def extract_recipe_names(recipes_dict):
    """Extract recipe names from a recipes dictionary, returning only the 'name' field."""
    if not recipes_dict:
        return []
    names = []
    for recipe in recipes_dict.values():
        if not isinstance(recipe, dict):
            continue
        name = (recipe.get('name') or '').strip()
        if name:
            names.append(name)
    return names


def fetch_menu():
    print(f'  [fetch_menu] GET {MENU_JSON_URL}', flush=True)
    resp = requests.get(MENU_JSON_URL, timeout=15)
    resp.raise_for_status()
    print(f'  [fetch_menu] HTTP {resp.status_code}, {len(resp.content)} bytes', flush=True)
    data = resp.json()

    def split_items(title_en):
        """Split a course title into individual dish names.

        Keep `w/...` fragments such as `w/smetana` intact instead of treating
        that slash as a dish separator.
        """
        if not title_en or title_en.strip() == 'N/A':
            return []
        return [t.strip() for t in re.split(r'(?<!\bw)/', title_en, flags=re.IGNORECASE) if t.strip()]

    timeperiod = data.get('timeperiod', 'N/A')
    days = []
    for day_data in data.get('mealdates', []):
        date_fi = day_data.get('date', '')
        courses = day_data.get('courses', {})
        c1 = courses.get('1', {})
        c2 = courses.get('2', {})
        days.append({
            'date': DAY_NAMES.get(date_fi, date_fi),
            'c1_items':    split_items(c1.get('title_en', '')),
            'c1_fi_items': split_items(c1.get('title_fi', '')),
            'c1_price': c1.get('price', 'N/A'),
            'c1_recipes': extract_recipe_names(c1.get('recipes', {})),
            'c2_items':    split_items(c2.get('title_en', '')),
            'c2_fi_items': split_items(c2.get('title_fi', '')),
            'c2_price': c2.get('price', 'N/A'),
            'c2_recipes': extract_recipe_names(c2.get('recipes', {})),
        })
    return timeperiod, days


def translate_days(days):
    """
    Translate all dish titles in one bulk API call using Finnish source titles
    (more semantically precise than English), then map results back by position.
    """
    # Use Finnish titles as translation input — they are the original names
    # and yield more accurate Chinese translations than the English versions.
    fi_titles = []
    for day in days:
        fi_titles.extend(day['c1_fi_items'])
        fi_titles.extend(day['c2_fi_items'])

    # Translate all Finnish titles at once
    fi_to_zh = translate_menu_bulk(fi_titles)

    def map_zh(en_items, fi_items):
        """Zip en/fi pairs and return zh list.
        If Finnish translation succeeded, use it.
        If it failed (returned fi unchanged), fall back to en so that
        format_menu's `en == zh` failure detection still works.
        """
        result = []
        for en, fi in zip_longest(en_items, fi_items, fillvalue=''):
            source = fi if fi else en
            zh = fi_to_zh.get(source, source)
            # Translation failed: model returned the source string unchanged
            result.append(en if zh == source else zh)
        return result

    translated_days = []
    for day in days:
        translated_days.append({
            **day,
            'c1_items_zh': map_zh(day['c1_items'], day['c1_fi_items']),
            'c2_items_zh': map_zh(day['c2_items'], day['c2_fi_items']),
        })
    return translated_days


def explain_days(days):
    """
    Explain dishes in Chinese for readers unfamiliar with Western cuisine.

    Input source per day:
      - c1_fi_items / c2_fi_items: Finnish dish titles
      - c1_recipes / c2_recipes: extracted recipe component names

    Returns:
      list[day] with two new keys: c1_explain, c2_explain
    """
    if not days:
        return days

    fallback = '信息有限，请结合饮食标签和个人口味判断是否适合自己。'
    if translation_client is None:
        return [{**day, 'c1_explain': fallback, 'c2_explain': fallback} for day in days]

    entries = []
    for day in days:
        for prefix in ('c1', 'c2'):
            fi_items = [i.strip() for i in day.get(f'{prefix}_fi_items', []) if i and i.strip()]
            recipe_names = [r.strip() for r in day.get(f'{prefix}_recipes', []) if r and r.strip()]
            dish_line = ' / '.join(fi_items) if fi_items else 'N/A'
            recipe_line = ' / '.join(recipe_names) if recipe_names else 'N/A'
            entries.append((dish_line, recipe_line))

    user_lines = []
    for idx, (dish_line, recipe_line) in enumerate(entries, start=1):
        user_lines.append(
            f'[{idx}] 菜名(芬兰语): {dish_line}\n'
            f'配方名称: {recipe_line}'
        )
    bulk_text = '\n\n'.join(user_lines)

    print(f'  [explain] Calling {MODEL_URL} model={TRANSLATION_MODEL}, {len(entries)} course entries...', flush=True)
    try:
        response = translation_client.chat.completions.create(
            model=TRANSLATION_MODEL,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a Western menu explanation assistant. '
                        'I will provide multiple entries of "dish name (in Finnish) + recipe component names". '
                        'For each numbered entry, write a brief Chinese explanation for readers unfamiliar with Western cuisine, so they can decide whether the dish suits them. '
                        'Keep each explanation within 2-3 sentences and include: key ingredients/flavor profile, and a suitability note (who it is suitable or unsuitable for). '
                        'Sauce is very important in Western dishes: if a sauce is present or implied, explain the sauce style, typical ingredients, and expected taste (for example creamy/tangy/herby/savory). '
                        'If the exact sauce recipe is unknown, state it as an informed estimate based on the dish/recipe names. '
                        'If information is insufficient, explicitly write "信息不足，建议现场确认过敏原". '
                        'Output must strictly follow this format: [number] explanation. '
                        'One line per entry only; do not output extra titles, notes, or blank lines.'
                    )
                },
                {'role': 'user', 'content': bulk_text},
            ],
            temperature=0.2,
        )
        explained_text = response.choices[0].message.content or ''
        print(f'  [explain] API response received ({len(explained_text)} chars)', flush=True)
        explained_lines = _clean_translation_lines(explained_text)
    except Exception as e:
        print(f'  [explain] API call failed: {e}', flush=True)
        explained_lines = []

    normalized = []
    for line in explained_lines:
        normalized.append(re.sub(r'^\[\d+\]\s*', '', line).strip())

    if len(normalized) > len(entries):
        normalized = normalized[:len(entries)]
    elif len(normalized) < len(entries):
        normalized.extend([fallback] * (len(entries) - len(normalized)))

    explained_days = []
    i = 0
    for day in days:
        explained_days.append({
            **day,
            'c1_explain': normalized[i] if normalized[i] else fallback,
            'c2_explain': normalized[i + 1] if normalized[i + 1] else fallback,
        })
        i += 2
    return explained_days


def format_menu_html(timeperiod, days):
    """Render the weekly menu by filling the email_render.html template."""
    e = html_lib.escape  # shorthand
    template_path = os.path.join(os.path.dirname(__file__), 'email_render.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    def render_dishes(items_en, items_zh):
        parts = []
        for en, zh in zip(items_en, items_zh):
            failed = (en == zh)
            zh_text = e(en) + '（翻译失败）' if failed else e(zh)
            parts.append(
                '<div class="dish">'
                '  <div class="dish-dot"></div>'
                '  <div>'
                f'    <div class="dish-en">{e(en)}</div>'
                f'    <div class="dish-zh">{zh_text}</div>'
                '  </div>'
                '</div>'
            )
        return ''.join(parts)

    day_blocks = []
    for day in days:
        # '📅 MONDAY · 周一'  →  day_en='📅 MONDAY'  day_zh='周一'
        parts = day['date'].split(' · ', 1)
        day_en = e(parts[0]) if parts else e(day['date'])
        day_zh = e(parts[1]) if len(parts) > 1 else ''

        c1 = render_dishes(day['c1_items'], day['c1_items_zh'])
        c2 = render_dishes(day['c2_items'], day['c2_items_zh'])
        c1_explain = e(day.get('c1_explain', ''))
        c2_explain = e(day.get('c2_explain', ''))

        day_blocks.append(
            '<div class="day-block">'
            '  <div class="day-header">'
            f'    <div class="day-name">{day_en} <span>{day_zh}</span></div>'
            '  </div>'
            '  <div class="course">'
            '    <div class="course-header">'
            '      <span class="course-title">🍽️ Favourites</span>'
            f'      <span class="course-price">{e(day["c1_price"])}</span>'
            f'    </div>{c1}'
            f'    <div class="course-explain">{c1_explain}</div>'
            '  </div>'
            '  <div class="course">'
            '    <div class="course-header">'
            '      <span class="course-title">👨‍🍳 Food Market</span>'
            f'      <span class="course-price">{e(day["c2_price"])}</span>'
            f'    </div>{c2}'
            f'    <div class="course-explain">{c2_explain}</div>'
            '  </div>'
            '</div>'
        )

    return (
        template
        .replace('{{TIMEPERIOD}}', e(timeperiod))
        .replace('{{DAY_BLOCKS}}', ''.join(day_blocks))
        .replace('{{RESTAURANT_URL}}', e(RESTAURANT_URL))
        .replace('{{TRANSLATION_MODEL}}', e(TRANSLATION_MODEL))
    )


def _unsubscribe_url(recipient):
    """Build a mailto: unsubscribe link pre-filled for the given recipient."""
    from urllib.parse import quote
    subject = quote('Unsubscribe from MenuMoose')
    body = quote(f'请将我的邮箱 {recipient} 从 MenuMoose 订阅中移除，谢谢！\n'
                 f'Please remove {recipient} from the MenuMoose mailing list. Thanks!')
    return f'mailto:qiang.1.huang@nokia.com?subject={subject}&body={body}'


def send_menu_email(timeperiod, days, recipients):
    subject = f'Nokia Linnanmaa Oulu Weekly Menu — {timeperiod}'
    body_html_template = format_menu_html(timeperiod, days)

    if not recipients:
        raise ValueError('No recipients configured for current mode.')

    if not RESEND_API_KEY:
        raise ValueError('RESEND_API_KEY environment variable not set.')

    resend.api_key = RESEND_API_KEY

    print(f'  [resend] Sending to {len(recipients)} recipient(s)...', flush=True)

    for recipient in recipients:
        unsub_url = _unsubscribe_url(recipient)
        body_html = body_html_template.replace('{{UNSUBSCRIBE_URL}}', html_lib.escape(unsub_url))

        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": recipient,
            "subject": subject,
            "html": body_html,
            "headers": {
                "List-Unsubscribe": f"<{unsub_url}>",
            },
        }
        email = resend.Emails.send(params)
        print(f'  [resend] Email sent to {recipient}: {email.get("id")}', flush=True)
        time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch, translate and email weekly menu.')
    parser.add_argument(
        '--white-list',
        action='store_true',
        help='Send only to recipients_test addresses in config.yml.'
    )
    args = parser.parse_args()
    recipients = RECIPIENTS_TEST if args.white_list else RECIPIENTS

    if args.white_list:
        print(f'  [mode] White-list enabled: recipients_test ({len(recipients)} addresses)', flush=True)

    print('[1/5] Fetching menu...', flush=True)
    timeperiod, days = fetch_menu()
    print(f'[2/5] Menu fetched: {timeperiod}, {len(days)} days', flush=True)

    print('[3/5] Translating menu...', flush=True)
    days = translate_days(days)
    print('[4/5] Translation done. Generating dish explanations...', flush=True)
    days = explain_days(days)
    print('[5/5] Dish explanations done. Sending email...', flush=True)

    send_menu_email(timeperiod, days, recipients)
    print('Done. Email sent successfully.', flush=True)
