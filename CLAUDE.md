# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

MenuMoose fetches the Sodexo weekly menu for Nokia Linnanmaa Oulu, translates Finnish dish names to Chinese via DeepSeek API, generates AI dish explanations, and sends styled HTML emails to subscribers via Resend.

## Commands

```bash
# Install dependencies
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Set required env vars
export OPENAI_API_KEY="sk-your-deepseek-api-key"
export RESEND_API_KEY="re_your-resend-api-key"

# Run (send to all recipients in config.yml)
python menumoose.py

# Test mode (send only to recipients_test)
python menumoose.py --white-list

# Preview email HTML locally (no API calls, mock data)
python render_preview.py
```

No test suite or linter is configured in this project.

## Architecture

This is a single-file pipeline script. The execution order in `menumoose.py:__main__` is:

1. **`fetch_menu()`** — GETs Sodexo JSON, splits each course's `title_en` by `/` into individual dishes (using `(?<!\bw)/` to avoid splitting "w/smetana" etc.). Extracts Finnish titles and recipe names.
2. **`translate_days()`** — Collects all Finnish titles across all days, calls `translate_menu_bulk()` once with the DeepSeek API, maps results back by position. Uses Finnish as source (not English) for better translation accuracy.
3. **`explain_days()`** — Sends Finnish dish names + recipe names to DeepSeek in one bulk call, gets 2-3 sentence Chinese explanations covering ingredients, flavor profile, and suitability.
4. **`format_menu_html()`** — Reads `email_render.html` template, replaces `{{PLACEHOLDER}}` tokens with rendered day/course/dish blocks.
5. **`send_menu_email()`** — Sends via Resend API to each recipient individually with a `List-Unsubscribe` header, 1-second delay between sends to respect 5 req/s rate limit.

### Key design decisions

- **Translation uses Finnish titles, not English.** The Sodexo JSON has both `title_en` and `title_fi`. Finnish terms are more precise (e.g., "Kirjolohi" → 虹鳟 rather than generic "salmon"), so `translate_days()` passes `c1_fi_items`/`c2_fi_items` to `translate_menu_bulk()`.
- **Bulk API calls (not per-dish).** All dishes across the week are translated in one call, and all explanations are generated in one call. This minimizes API latency and cost.
- **In-memory translation cache** (`translation_cache` dict) avoids re-translating repeated dishes within a run.
- **Partial success tolerance.** If the API returns fewer/more lines than expected, the code truncates extras or pads with originals rather than failing.
- **Zscaler/enterprise proxy support.** `_make_openai_client()` uses `ssl.get_default_verify_paths()` to load the system CA bundle instead of `certifi` defaults, needed for corporate MITM proxies.
- **Translation failure detection.** In `format_menu_html()`, if the translated string equals the original English string, the code marks it as "翻译失败" (translation failed) rather than silently displaying wrong text.

### Files

| File | Role |
|---|---|
| `menumoose.py` | Main pipeline (all logic in one file) |
| `email_render.html` | HTML email template with `{{TIMEPERIOD}}`, `{{DAY_BLOCKS}}`, `{{RESTAURANT_URL}}`, `{{TRANSLATION_MODEL}}`, `{{UNSUBSCRIBE_URL}}` placeholders |
| `render_preview.py` | Generates `preview_rendered.html` with mock data for local template editing |
| `config.yml` | Non-sensitive config (recipients, model, URLs) — version-controlled |
| `.env.example` | Template for required env vars |
| `.github/workflows/menumoose.yml` | CI: runs every Monday UTC 04:00 (Helsinki ~07:00), manual trigger supported |

### Sensitive config

- `OPENAI_API_KEY` — DeepSeek API key (env var, goes to GitHub Secrets)
- `RESEND_API_KEY` — Resend API key (env var, goes to GitHub Secrets)
- `config.yml` — NOT sensitive, version-controlled (recipients, model, URLs)

## Constraints when making changes

- Do not install `certifi` or hardcode CA paths — the project deliberately uses the system CA bundle for corporate proxy compatibility.
- Keep the single-file architecture unless there's a compelling reason to split. The script is ~490 lines and reasonably organized.
- The email is HTML-only (no plaintext fallback). All content rendering uses `html_lib.escape()`.
- Finnish cuisine terminology matters: "Kirjolohi" = 虹鳟, "Riista" = 野味/鹿肉, etc. See `translate_menu_bulk()` system prompt.
