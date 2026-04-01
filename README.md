# MenuMoose

自动获取 Nokia Linnanmaa Oulu 每周菜单，使用 AI 将菜名翻译为中文，并发送 HTML 风格邮件给订阅用户。

MenuMoose fetches Sodexo weekly menu data, translates dish names to Chinese, and sends styled HTML email updates.

---

## 功能特性

- 每周自动运行（GitHub Actions）
- 菜名双语显示（英文 + 中文）
- 每个 Course 自动拆分多道菜（按 / 分割）
- 使用芬兰语原始菜名作为翻译输入，提高中文准确性
- HTML 邮件模板渲染（来自独立模板文件）
- 收件人隐私保护（不在邮件头暴露列表）
- 企业网络兼容（系统 CA bundle，适配 Zscaler）
- SMTP 465（SMTPS）稳定发送

---

## 项目结构

MenuMoose/
- .github/workflows/menumoose.yml
- config.yml
- menumoose.py
- email_render.html
- render_preview.py
- preview_rendered.html
- example.json
- requirements.txt
- README.md

说明：
- email_render.html: 邮件 HTML 模板（含占位符）
- render_preview.py: 本地注入虚拟数据并生成预览
- preview_rendered.html: 本地预览输出文件

---

## 配置说明

### 1. config.yml（非敏感配置，纳入版本管理）

- `recipients`: 收件人列表
- `menu_url`: Sodexo 周菜单 JSON 地址
- `smtp.server` / `smtp.port`: SMTP 服务器与端口（推荐 465，直接 SSL）
- `translation.model` / `translation.api_base`: 翻译模型与 API Base URL
- `restaurant`、`mystery_box`: 邮件展示信息

示例：

```yaml
recipients:
  - your.name@example.com

menu_url: "https://www.sodexo.fi/ruokalistat/output/weekly_json/3207223"

smtp:
  server: "smtp.gmail.com"
  port: 465          # 465=SMTPS(推荐)  587=STARTTLS

translation:
  model: "stepfun/step-3.5-flash:free"
  api_base: "https://openrouter.ai/api/v1"
```

### 2. GitHub Secrets（敏感信息）

在仓库 Settings → Secrets and variables → Actions 中配置：

| Secret | 说明 |
|---|---|
| `MENU_SMTP_USER` | 发件邮箱地址 |
| `MENU_SMTP_PASS` | Gmail 应用专用密码 |
| `OPENAI_API_KEY` | OpenRouter / OpenAI API Key |

---

## GitHub Actions 工作流

文件位置：[.github/workflows/menumoose.yml](.github/workflows/menumoose.yml)

- 定时：每周一 UTC 06:00（赫尔辛基约 08:00）
- 支持：手动触发（workflow_dispatch）

流程：

1. 拉取 Sodexo JSON 菜单
2. 提取每天 Course 1/2，按 `/` 拆分为独立菜品列表
3. 批量翻译全周所有菜名（1 次 API 调用）
4. 生成纯文本邮件正文
5. 通过 SMTP 465（SMTPS）发送给配置收件人

---

## 邮件格式示例

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   NOKIA LINNANMAA OULU  |  Weekly Menu 每周菜单
   23.3. — 29.3.
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

饮食标签 | DIET LABELS
G: Gluten free 无麸质  L: Lactose free 无乳糖  M: Milk-free 无奶制品  VL: Low lactose 低乳糖

📅 MONDAY · 周一
──────────────────────────────────────────────────
🌟 FAVOURITES  |  8,80€
   • Butter chicken (L,G)
     黄油鸡
   • Tofu in chili-sesame sauce (M,G)
     辣味芝麻豆腐

🛒 FOOD MARKET  |  11,80€
   • Breaded fishrolls (M), tartar sauce (M,G)
     面包糠鱼卷配鞑靼酱
   • Chickpea patties (M,G,V)
     鹰嘴豆饼
──────────────────────────────────────────────────
```

---

## 本地运行

### 安装依赖

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 设置环境变量

```bash
export MENU_SMTP_USER="sender@gmail.com"
export MENU_SMTP_PASS="your-app-password"
export OPENAI_API_KEY="your-api-key"
```

### 运行（含调试输出）

```bash
python menumoose.py
```

运行时会打印各步骤进度，便于定位超时或连接问题：

```
[1/4] Fetching menu...
  [fetch_menu] GET https://...
  [fetch_menu] HTTP 200, 90779 bytes
[2/4] Menu fetched: 23.3. - 29.3., 5 days
[3/4] Translating menu...
  [translate] Calling https://openrouter.ai/api/v1 model=..., 10 titles...
  [translate] API response received (407 chars)
[4/4] Translation done. Sending email...
  [smtp] Connecting to smtp.gmail.com:465...
Done. Email sent successfully.
```

---

## 企业网络 / Zscaler 兼容

本地开发环境若通过 Zscaler 等 MITM 代理上网，代码会自动使用系统 CA bundle（而非 `certifi` 内置 CA）来完成 SSL 验证：

- **翻译 API**：`_make_openai_client()` 使用 `ssl.get_default_verify_paths()` 获取系统 CA 路径，注入 `httpx.Client`
- **SMTP**：`ssl.create_default_context(cafile=system_ca)` 传入 `SMTP_SSL`

**推荐使用 SMTP 端口 465**（SMTPS 直接 SSL）。587 的 STARTTLS 在某些企业防火墙下 TLS 握手会超时。

GitHub Actions 环境无代理限制，相同代码直接可用。

---

## 常见问题排查

### 翻译失败 / Connection error

- 确认 `OPENAI_API_KEY` 有效且对应当前 `api_base` 服务商
- 企业网络下用 `curl -X POST https://openrouter.ai/api/v1/chat/completions ...` 验证网络可达性
- 检查是否有代理环境变量：`echo $HTTPS_PROXY`

### 收不到邮件 / SMTP 超时

- 优先使用端口 `465`（SMTPS），比 587 更稳定
- 用 `openssl s_client -connect smtp.gmail.com:465` 验证端口可达
- 确认 Gmail 已开启"应用专用密码"

### 菜单为空或缺失

- 检查 `menu_url` 是否有效
- Sodexo 接口结构变化时需更新 `fetch_menu()` 解析逻辑

---

## 主要函数

- fetch_menu(): 拉取并解析每周菜单，提取英/芬菜名
- translate_menu_bulk(): 批量翻译条目
- translate_days(): 以芬兰语为输入映射到中文
- format_menu_html(): 读取 email_render.html 并渲染动态内容
- send_menu_email(): 组装并发送 HTML 邮件
---

## 更新日志

### 2026-04-01
- 邮件发送切换为 HTML only
- README 对齐当前实现
- 文档补充模板预览流程与占位符说明

### 2026-03-31
- HTML 模板抽离为独立文件 email_render.html
- 新增 render_preview.py 本地虚拟渲染

### 2026-03-30
- 支持 Outlook 兼容样式调整
- 支持模板内 Powered by 链接与 footer 布局调整

### 2026-03-29
- 菜单改为每道菜独立显示
- 翻译输入改为芬兰语原文

### v1.2.0 (2026-03-29)
- 菜单排版重构：每道菜独立 `• 英文 / 中文` 两行展示，替代原单行合并格式
- `fetch_menu()` 新增按 `/` 拆分同课程多菜品逻辑
- 日期标题格式更新：`MONDAY · 周一`

### v1.1.1 (2026-03-28)
- SMTP 端口改为 465（SMTPS），修复 Zscaler 环境下 587 STARTTLS 握手超时
- `_make_openai_client()` 新增系统 CA bundle 注入，修复企业代理 SSL 验证失败
- 全流程新增 `print(..., flush=True)` 调试输出，便于定位超时步骤

### v1.1.0 (2026-03-26)
- 配置迁移：非敏感配置统一放入 `config.yml`
- 邮件隐私优化：收件人地址不在邮件头中暴露
- 翻译稳定性优化：增强模型输出清洗与部分成功兜底

### v1.0.0
- 初始版本发布

