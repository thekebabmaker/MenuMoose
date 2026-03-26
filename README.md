# MenuMoose 🍽️

自动每周获取 Nokia Linnanmaa Oulu 食堂菜单，通过 AI 翻译英文菜名为中文，并发送中英双语邮件给订阅用户。

Automated weekly lunch menu sender for Sodexo Nokia Linnanmaa. It fetches weekly JSON menu data, translates English dish names into Chinese, and sends bilingual email updates to subscribers.

---

## 功能特性 ✨

- 📅 每周一自动运行（GitHub Actions）
- 🇬🇧🇨🇳 菜名双语展示：一行英文 + 一行中文
- 🧾 纯文本邮件模板，阅读稳定、兼容性高
- 🔒 收件人隐私保护：邮件头不暴露订阅名单
- 🚀 批量翻译：一次请求翻译整周菜名
- 🛡️ 翻译容错：部分失败时保留部分翻译结果
- ⚠️ 翻译兜底提示：若翻译失败，中文行会标注“（翻译失败）”

---

## 项目结构 📁

```text
MenuMoose/
├── .github/
│   └── workflows/
│       └── menumoose.yml
├── config.yml
├── menumoose.py
├── requirements.txt
└── README.md
```

---

## 配置说明 ⚙️

### 1. config.yml（非敏感配置，纳入版本管理）

- `recipients`: 收件人列表
- `menu_url`: Sodexo 周菜单 JSON 地址
- `smtp.server` / `smtp.port`: SMTP 服务器与端口
- `translation.model` / `translation.api_base`: 模型与 API Base URL
- `restaurant`、`mystery_box`: 邮件展示信息

示例（精简）：

```yaml
recipients:
  - your.name@example.com

menu_url: "https://www.sodexo.fi/ruokalistat/output/weekly_json/3207223"

smtp:
  server: "smtp.gmail.com"
  port: 587

translation:
  model: "stepfun/step-3.5-flash:free"
  api_base: "https://openrouter.ai/api/v1"
```

### 2. GitHub Secrets（敏感信息）

在仓库 Settings → Secrets and variables → Actions 中配置：

- `MENU_SMTP_USER`
- `MENU_SMTP_PASS`
- `OPENAI_API_KEY`

说明：当前实现不再使用 `MENU_EMAIL_LIST`、`MENU_SMTP_SERVER`、`MENU_SMTP_PORT` 这类 secrets，这些已迁移到 `config.yml`。

---

## GitHub Actions 工作流 ⏰

文件位置：[.github/workflows/menumoose.yml](.github/workflows/menumoose.yml)

- 定时：每周一 UTC 06:00（赫尔辛基约 08:00）
- 支持：手动触发（workflow_dispatch）

流程：

1. 拉取 Sodexo JSON 菜单
2. 提取每天的 course 1/2 英文菜名和价格
3. 批量翻译菜名为中文
4. 生成邮件正文（英文行 + 中文行）
5. 通过 SMTP 发送给配置收件人

---

## 邮件格式示例 📧

```text
╔════════════════════════════════════════╗
║  Nokia Linnanmaa Oulu — Weekly Menu / 每周菜单
║  24.3. - 28.3.
╚════════════════════════════════════════╝

  饮食标签说明:
  G: Gluten free无麸质  L: Lactose free无乳糖  M: Milk-free无奶制品  VL: Low lactose低乳糖

  📅 Monday / 周一
  ──────────────────────────────────────────────────────────────────
    🌟 FAVOURITES
       Butter chicken (L,G)
       黄油鸡 (L,G)
       💰 8,80€

    🛒 FOOD MARKET
       Breaded fishrolls (M), tartar sauce
       面包糠炸鱼卷 (M)，鞑靼酱
       💰 11,80€
```

如果翻译失败，第二行会显示：

```text
Butter chicken (L,G)（翻译失败）
```

---

## 本地运行 👨‍💻

### 安装依赖

```bash
pip install -r requirements.txt
```

### 设置环境变量

```bash
export MENU_SMTP_USER="sender@example.com"
export MENU_SMTP_PASS="smtp-password-or-app-password"
export OPENAI_API_KEY="your-api-key"
```

### 运行

```bash
python menumoose.py
```

---

## 常见问题排查 🔧

### 1) 邮件出现两行英文（没有中文）

常见原因：

- `OPENAI_API_KEY` 不可用 / 失效
- 模型临时不可用或响应异常
- 触发翻译兜底逻辑

检查项：

- Actions 日志里是否有 API 错误
- `translation.model` 与 `translation.api_base` 是否匹配
- `OPENAI_API_KEY` 是否对应当前服务商（OpenRouter/OpenAI）

### 2) 收不到邮件

- 检查 `MENU_SMTP_USER` / `MENU_SMTP_PASS`
- 检查 `smtp.server` / `smtp.port`
- 检查垃圾邮件文件夹

### 3) 菜单为空或缺失

- 检查 `menu_url` 是否有效
- Sodexo 接口结构变化时需更新解析逻辑

---

## 主要函数说明 🧩

- `fetch_menu()`: 拉取并解析周菜单 JSON
- `translate_menu_bulk()`: 批量翻译英文菜名
- `translate_days()`: 将翻译映射回每日菜单
- `format_menu()`: 拼接邮件正文
- `send_menu_email()`: 发送邮件（隐藏收件人）

---

## 更新日志 📝

### v1.1.0 (2026-03-26)

- 配置迁移：非敏感配置统一放入 `config.yml`
- 邮件隐私优化：收件人地址不在邮件头中暴露
- 翻译稳定性优化：增强模型输出清洗与部分成功兜底
- 邮件头部恢复饮食标签说明

### v1.0.0

- 初始版本发布
- 支持每周自动获取菜单并翻译后发送邮件
