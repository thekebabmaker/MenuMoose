import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- CONFIG ---
EMAIL_LIST = os.environ.get('MENU_EMAIL_LIST', '').split(',')  # comma-separated
SMTP_SERVER = os.environ.get('MENU_SMTP_SERVER', 'smtp.example.com')
SMTP_PORT = int(os.environ.get('MENU_SMTP_PORT', '587'))
SMTP_USER = os.environ.get('MENU_SMTP_USER', 'user@example.com')
SMTP_PASS = os.environ.get('MENU_SMTP_PASS', 'password')

MENU_JSON_URL = 'https://www.sodexo.fi/ruokalistat/output/weekly_json/3207223'

# Finnish weekday names -> English
DAY_NAMES = {
    'Maanantai': 'Monday',
    'Tiistai': 'Tuesday',
    'Keskiviikko': 'Wednesday',
    'Torstai': 'Thursday',
    'Perjantai': 'Friday',
    'Lauantai': 'Saturday',
    'Sunnuntai': 'Sunday',
}

# --- FETCH & PARSE MENU ---
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

# --- FORMAT WEEKLY MENU ---
def format_menu(timeperiod, days):
    separator = '=' * 56
    lines = [
        f'Nokia Linnanmaa — Weekly Menu  {timeperiod}',
        separator,
        '',
    ]
    for day in days:
        lines.append(f"  {day['date']}")
        lines.append(f"    1. FAVOURITES  : {day['c1_title']}")
        lines.append(f"                     {day['c1_price']}")
        lines.append(f"    2. FOOD MARKET : {day['c2_title']}")
        lines.append(f"                     {day['c2_price']}")
        lines.append('')
    lines.append(separator)
    return '\n'.join(lines)

# --- SEND EMAIL ---
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
    send_menu_email(timeperiod, days)
