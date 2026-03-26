# MenuMoose 🍽️

自动每周获取诺基亚 Linnanmaa 食堂菜单，通过 AI 翻译成中文，并发送邮件到订阅用户。

**English:** Automated weekly lunch menu sender for Sodexo Nokia Linnanmaa. Fetches the weekly JSON menu every Monday morning, translates English dishes to Chinese via AI, and emails bilingual menu to subscribers.

---

## 功能特性 ✨

- 📅 **定时触发**：每周一早上 8:00（赫尔辛基时间）自动运行
- 🇬🇧🇨🇳 **双语翻译**：英文菜名自动翻译成自然流畅的中文
- 📧 **邮件发送**：格式化的周菜单发送给可配置的收件人列表
- 🚀 **单次 API 调用**：所有菜名一次批量翻译，节省成本
- 💾 **智能缓存**：翻译结果缓存，减少重复调用
- 🔄 **故障容错**：翻译失败自动降级到原英文，不影响邮件发送
- 📱 **GitHub Actions**：完全托管，无需自建服务器

---

## 快速开始 🚀

### 前提条件

- GitHub 账号和仓库
- OpenAI/OpenRouter API Key（用于菜单翻译）
- SMTP 邮箱账户（用于发送邮件）

### 1. 克隆仓库到你的环境

```bash
git clone https://github.com/yourusername/MenuMoose.git
cd MenuMoose
```

### 2. 配置 GitHub Secrets

在仓库 **Settings → Secrets and variables → Actions** 中创建以下 secrets：

| Secret 名称 | 示例值 | 说明 |
|---|---|---|
| `MENU_EMAIL_LIST` | `alice@example.com,bob@example.com` | 逗号分隔的收件人列表 |
| `MENU_SMTP_SERVER` | `smtp.gmail.com` | SMTP 服务器地址 |
| `MENU_SMTP_PORT` | `587` | SMTP 端口（通常 587） |
| `MENU_SMTP_USER` | `sender@gmail.com` | 发件人邮箱 |
| `MENU_SMTP_PASS` | `your-app-password` | 邮箱授权码或应用密码 |
| `OPENAI_API_KEY` | `sk-...` 或 OpenRouter key | AI 翻译 API Key |

#### 邮箱配置参考

**Gmail**
- `MENU_SMTP_SERVER`: `smtp.gmail.com`
- `MENU_SMTP_PORT`: `587`
- `MENU_SMTP_PASS`: 需在 [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) 生成 App Password

**Outlook / Microsoft 365**
- `MENU_SMTP_SERVER`: `smtp.office365.com`
- `MENU_SMTP_PORT`: `587`
- `MENU_SMTP_PASS`: 你的邮箱密码

#### AI 翻译配置参考

**OpenRouter (推荐)**
- `OPENAI_API_KEY`: 从 [openrouter.ai](https://openrouter.ai) 获取
- 支持免费模型，成本最低

**OpenAI (官方)**
- `OPENAI_API_KEY`: 从 [platform.openai.com](https://platform.openai.com) 获取
- 需要绑定支付方式

### 3. 手动测试（可选）

在 Actions 页面点击 **Run workflow** 手动触发一次，验证配置是否正确。

---

## 工作流说明 📋

### 触发条件

- **定时触发**：每周一 UTC 06:00（赫尔辛基冬令时 08:00）
- **手动触发**：在 GitHub Actions 页面点击 "Run workflow"

### 执行流程

```
1. 从 Sodexo API 拉取周菜单 JSON
   ↓
2. 解析菜单，提取英文菜名
   ↓
3. 调用 AI 一次性翻译所有菜名为中文
   ↓
4. 生成格式化的中英双语菜单
   ↓
5. 通过 SMTP 发送邮件给收件人
```

### 邮件内容示例

```
╔════════════════════════════════════════════════════╗
║  Nokia Linnanmaa Oulu — Weekly Menu / 每周菜单      ║
║  Date / 日期: 24.3. - 28.3.                         ║
╚════════════════════════════════════════════════════╝

  📅 Monday / 周一
  ────────────────────────────────────────────────────
    🌟 FAVOURITES
       EN : Butter chicken (L,G) / Tofu in chili-sesame
       中 : 黄油鸡 (L,G) / 辣芝麻豆腐
       💰 8,80€

    🛒 FOOD MARKET
       EN : Breaded fishrolls(M), tartar sauce
       中 : 面包糠炸鱼卷(M)，鞑靼酱
       💰 11,80€

  ────────────────────────────────────────────────────
  🤖 中文翻译由 stepfun/step-3.5-flash:free 模型提供
  🔗 菜单来源: www.sodexo.fi/ravintolat/nokia-linnanmaa
  📦 剩菜盲盒: 周一到周五, 13.00-13.10, 7,70€/kg
  📬 Bon appétit! 祝您用餐愉快！
```

---

## 项目结构 📁

```
MenuMoose/
├── .github/
│   └── workflows/
│       └── menumoose.yml          # GitHub Actions 工作流配置
├── menumoose.py                    # 主程序
├── requirements.txt                # Python 依赖（可选）
├── README.md                       # 本文件
└── .gitignore
```

---

## 配置文件说明 ⚙️

### menumoose.yml

工作流配置文件，定义何时运行以及运行步骤：

```yaml
on:
  schedule:
    - cron: '0 6 * * 1'  # 每周一 UTC 06:00
  workflow_dispatch:     # 支持手动触发
```

修改 cron 表达式可改变执行时间：
- `0 6 * * 1` = 每周一 06:00
- `0 8 * * 1` = 每周一 08:00
- `0 18 * * *` = 每天 18:00

### menumoose.py

主程序文件，包含以下主要函数：

| 函数 | 说明 |
|---|---|
| `fetch_menu()` | 从 Sodexo API 拉取菜单 JSON |
| `translate_menu_bulk()` | 批量翻译菜名 |
| `translate_days()` | 应用翻译结果到每日菜单 |
| `format_menu()` | 生成格式化邮件正文 |
| `send_menu_email()` | 通过 SMTP 发送邮件 |

---

## 故障排查 🔧

### 收不到邮件

1. **检查 SMTP 配置**
   - 验证 `MENU_SMTP_SERVER` 和 `MENU_SMTP_PORT` 是否正确
   - Gmail 需要使用 **App Password**（不是登录密码）

2. **检查收件人地址**
   - 确保 `MENU_EMAIL_LIST` 格式正确，多个地址用逗号分隔
   - 检查 spam / 垃圾邮件文件夹

3. **查看 Actions 日志**
   - 在 GitHub Actions 页面查看运行日志
   - 寻找 "SMTP" 或 "authentication" 相关错误

### 翻译失败

1. **检查 API Key**
   - 验证 `OPENAI_API_KEY` 是否正确
   - OpenRouter 需要绑定有效支付方式

2. **查看日志**
   - 脚本会自动降级到英文，不影响邮件发送
   - 检查是否有关于 API 调用的错误信息

3. **模型不可用**
   - 如果使用的免费模型不可用，需改用其他模型
   - 修改 `menumoose.py` 中的 `TRANSLATION_MODEL` 变量

### 菜单为空

1. **验证 Sodexo API**
   - 检查 `MENU_JSON_URL` 是否仍然有效
   - Sodexo 可能更新过 API，需要更新 URL

2. **检查 JSON 结构**
   - 在浏览器访问 URL，查看 JSON 格式是否变化
   - 可能需要调整解析逻辑

---

## 开发和本地测试 👨‍💻

### 安装依赖

```bash
pip install -r requirements.txt
```

### 本地运行

```bash
# 设置环境变量
export MENU_EMAIL_LIST="test@example.com"
export MENU_SMTP_SERVER="smtp.gmail.com"
export MENU_SMTP_PORT="587"
export MENU_SMTP_USER="sender@gmail.com"
export MENU_SMTP_PASS="your-app-password"
export OPENAI_API_KEY="sk-..."

# 运行脚本
python menumoose.py
```

### 调试

修改 `menumoose.py` 中的 cron 表达式为更频繁的运行时间，或直接注释掉 `send_menu_email()` 调用改为打印输出。

---

## 提示与小技巧 💡

- **降低成本**：使用 OpenRouter 免费模型，每周只调用一次，成本几乎为零
- **自定义邮件**：修改 `format_menu()` 函数可自定义邮件格式和内容
- **多餐厅支持**：可修改脚本支持多个 Sodexo 餐厅 ID（需多次调用）
- **缓存管理**：翻译缓存存于内存，每次运行重置。可改为文件缓存增加效率

---

## 许可证 📄

MIT License

---

## 贡献 🤝

欢迎提交 Issue 或 Pull Request！

---

## 联系方式 📧

如有问题，请在 GitHub Issues 中提出。

---

## 更新日志 📝

### v1.0.0 (2026-03-26)
- 初始版本发布
- 支持英文菜单翻译
- 邮件发送功能
- GitHub Actions 定时触发
