#!/usr/bin/env python3
"""Render email template with mock placeholders for local design/testing.

Usage:
  python render_preview.py

Output:
  preview_rendered.html
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "email_render.html"
OUTPUT_PATH = ROOT / "preview_rendered.html"

MOCK_DAY_BLOCKS = """
<div class="day-block">
  <div class="day-header">
    <div class="day-name">📅 MONDAY <span>周一</span></div>
  </div>
  <div class="course">
    <div class="course-header">
      <span class="course-title">🌟 Favourites</span>
      <span class="course-price">8,80€</span>
    </div>
    <div class="dish">
      <div class="dish-dot"></div>
      <div>
        <div class="dish-en">Pork stew with honey &amp; beet root (G,L)</div>
        <div class="dish-zh">蜂蜜甜菜根炖猪肉</div>
      </div>
    </div>
    <div class="dish">
      <div class="dish-dot"></div>
      <div>
        <div class="dish-en">Spicy lentil stew (G,M)</div>
        <div class="dish-zh">辣扁豆炖菜</div>
      </div>
    </div>
  </div>
  <div class="course">
    <div class="course-header">
      <span class="course-title">🛒 Food Market</span>
      <span class="course-price">11,80€</span>
    </div>
    <div class="dish">
      <div class="dish-dot"></div>
      <div>
        <div class="dish-en">Pan patty with cream sauce (G,L)</div>
        <div class="dish-zh">香煎肉饼配奶油酱</div>
      </div>
    </div>
    <div class="dish">
      <div class="dish-dot"></div>
      <div>
        <div class="dish-en">Vegetable patties with herb yogurt (G,L)</div>
        <div class="dish-zh">蔬菜饼配香草酸奶</div>
      </div>
    </div>
  </div>
</div>

<div class="day-block">
  <div class="day-header">
    <div class="day-name">📅 TUESDAY <span>周二</span></div>
  </div>
  <div class="course">
    <div class="course-header">
      <span class="course-title">🌟 Favourites</span>
      <span class="course-price">8,80€</span>
    </div>
    <div class="dish">
      <div class="dish-dot"></div>
      <div>
        <div class="dish-en">Red Thai curry with chicken (M,G)</div>
        <div class="dish-zh">泰式红咖喱鸡</div>
      </div>
    </div>
    <div class="dish">
      <div class="dish-dot"></div>
      <div>
        <div class="dish-en">Lentil-vegetable bolognese (M,G)</div>
        <div class="dish-zh">扁豆蔬菜波隆那酱</div>
      </div>
    </div>
  </div>
  <div class="course">
    <div class="course-header">
      <span class="course-title">🛒 Food Market</span>
      <span class="course-price">11,80€</span>
    </div>
    <div class="dish">
      <div class="dish-dot"></div>
      <div>
        <div class="dish-en">Pork schnitzel &amp; chili mayo (M)</div>
        <div class="dish-zh">德式炸猪排配辣味蛋黄酱</div>
      </div>
    </div>
    <div class="dish">
      <div class="dish-dot"></div>
      <div>
        <div class="dish-en">Vegetable moussaka (L)</div>
        <div class="dish-zh">蔬菜慕萨卡</div>
      </div>
    </div>
  </div>
</div>
""".strip()


def main() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = (
        template.replace("{{TIMEPERIOD}}", "23.3. - 29.3.")
        .replace("{{DAY_BLOCKS}}", MOCK_DAY_BLOCKS)
        .replace("{{RESTAURANT_URL}}", "https://www.sodexo.fi/ravintolat/nokia-linnanmaa")
        .replace("{{TRANSLATION_MODEL}}", "qwen3.5-plus")
    )
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Rendered preview: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
