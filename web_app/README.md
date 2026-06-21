# Web App - Multi-Agent 购物调研系统

> 精美的 Web 可视化界面，支持用户登录、实时查询、历史记录管理。

---

## 🎨 特性

✅ **现代化 UI** - Bootstrap 5 + 渐变色 + 动画效果  
✅ **用户认证** - 注册、登录、个人资料管理  
✅ **实时查询** - 异步任务处理 + 进度反馈  
✅ **历史记录** - 查询历史、分页展示  
✅ **报告下载** - Markdown 报告导出  
✅ **响应式设计** - 完美适配手机和桌面  

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd E:\agentlearn\design\web_app
pip install -r requirements.txt
```

### 2. 配置密钥

确保 `.env` 文件已配置（已自动生成）：

```env
CLAUDE_API_KEY=sk-xxx
CLAUDE_API_BASE_URL=https://api.deepseek.com/anthropic
SECRET_KEY=your-secret-key-here
```

### 3. 运行应用

```bash
python app.py
```

访问 http://localhost:5000

---

## 📁 目录结构

```
web_app/
├── app.py                    # Flask 主应用
├── models.py                 # 数据库模型
├── config.py                 # 配置管理
├── .env                      # 环境变量（密钥）
├── .env.example              # 配置模板
├── requirements.txt          # 依赖清单
│
├── api/                      # API 路由
│   ├── auth.py              # 用户认证
│   └── routes.py            # 查询、历史等
│
├── static/                   # 静态文件
│   ├── css/
│   │   └── style.css        # 超精美样式
│   └── js/
│       ├── main.js          # 主 JS
│       └── dashboard.js     # 仪表盘 JS
│
├── templates/                # HTML 模板
│   ├── layout.html          # 基础布局
│   ├── index.html           # 首页
│   ├── dashboard.html       # 仪表盘
│   ├── history.html         # 历史记录
│   ├── result.html          # 结果展示
│   └── auth/
│       ├── login.html       # 登录
│       └── register.html    # 注册
│
├── sqlite/                   # 数据库（SQLite）
│   └── shopping_web.db
│
├── reports/                  # 生成的报告
└── uploads/                  # 上传文件
```

---

## 🎯 功能说明

### 1. 用户系统

- **注册**：用户名、邮箱、密码
- **登录**：支持"记住我"
- **权限控制**：未登录自动跳转登录页

### 2. 查询功能

- **输入关键词**：如 "iPhone 15 Pro"
- **选择平台**：闲鱼、淘宝、京东、拼多多（多选）
- **异步处理**：后台执行，前端轮询状态
- **进度反馈**：实时显示处理状态

### 3. 历史记录

- **分页展示**：每页 10 条
- **状态筛选**：等待中、处理中、已完成、失败
- **快速查看**：点击查看详情

### 4. 结果展示

- **统计数据**：商品数、平台数、耗时
- **报告下载**：Markdown 格式
- **图表展示**：（在下载的报告中）

---

## 🔧 技术栈

| 类别 | 技术 |
|------|------|
| 后端 | Flask 2.3+ |
| 数据库 | SQLite3 |
| ORM | Flask-SQLAlchemy |
| 认证 | Flask-Login |
| 前端 | Bootstrap 5, jQuery |
| 图标 | Font Awesome 6 |
| 字体 | Google Fonts (Inter) |

---

## ⚙️ 配置说明

### 环境变量（.env）

```env
# Claude API 配置
CLAUDE_API_KEY=sk-xxx              # API 密钥
CLAUDE_API_BASE_URL=https://xxx    # API 地址
CLAUDE_MODEL=claude-opus-4-7       # 模型

# Flask 配置
SECRET_KEY=xxx                     # Session 密钥（必须修改）
FLASK_ENV=development              # 开发/生产模式
FLASK_DEBUG=True                   # 调试模式

# 数据库
DATABASE_PATH=sqlite/shopping_web.db

# 任务配置
MAX_CONCURRENT_TASKS=3             # 最大并发任务数
TASK_TIMEOUT=300                   # 任务超时（秒）
CACHE_TTL=3600                     # 缓存时间（秒）
```

### 修改 API 密钥

**方法 1：直接编辑 `.env` 文件**

```bash
notepad .env
# 修改 CLAUDE_API_KEY 的值
```

**方法 2：通过代码修改**

编辑 `config.py`，硬编码密钥（不推荐）。

---

## 🎨 UI 特色

### 设计风格

- **现代渐变色**：紫色系主题
- **毛玻璃效果**：backdrop-filter 模糊
- **平滑动画**：fade-in-up、hover 效果
- **卡片式设计**：圆角、阴影
- **响应式布局**：移动端优化

### 配色方案

```css
主色：#6366f1 (靛蓝)
辅色：#8b5cf6 (紫色)
成功：#10b981 (绿色)
警告：#f59e0b (橙色)
危险：#ef4444 (红色)
```

---

## 📊 数据库结构

### users 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String(80) | 用户名（唯一） |
| email | String(120) | 邮箱（唯一） |
| password_hash | String(255) | 密码哈希 |
| created_at | DateTime | 创建时间 |
| last_login | DateTime | 最后登录 |

### query_history 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | Integer | 用户 ID |
| query | String(200) | 查询关键词 |
| platforms | String(100) | 平台列表 |
| products_count | Integer | 商品数量 |
| status | String(20) | 状态 |
| report_path | String(500) | 报告路径 |
| elapsed_time | Float | 耗时（秒） |
| result_data | Text | 结果数据（JSON） |
| created_at | DateTime | 创建时间 |
| completed_at | DateTime | 完成时间 |

---

## 🔒 安全注意事项

1. **修改 SECRET_KEY**：生产环境必须使用强随机密钥
2. **保护 .env 文件**：不要提交到 Git
3. **HTTPS**：生产环境启用 HTTPS
4. **输入验证**：已实现基础验证
5. **SQL 注入防护**：使用 ORM（SQLAlchemy）
6. **密码加密**：使用 Werkzeug 的 pbkdf2:sha256

---

## 🐛 常见问题

### 1. 数据库不存在

**解决**：自动创建，确保 `sqlite/` 目录存在

### 2. API 调用失败

**解决**：检查 `.env` 中的 `CLAUDE_API_KEY` 是否正确

### 3. 端口占用

```bash
# 修改端口
python app.py  # 默认 5000
# 或在 app.py 中修改：socketio.run(app, port=8000)
```

### 4. 前端样式不生效

**解决**：清除浏览器缓存，强制刷新（Ctrl+F5）

---

## 🚀 部署建议

### 生产环境

1. **使用 Gunicorn**

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

2. **使用 Nginx 反向代理**

3. **配置 HTTPS**（Let's Encrypt）

4. **使用 PostgreSQL**（替代 SQLite）

5. **启用日志**

---

## 📝 更新日志

### v1.0.0 (2026-06-17)

- ✅ 完成用户认证系统
- ✅ 实现查询功能
- ✅ 完成历史记录管理
- ✅ 精美 UI 设计
- ✅ 响应式布局

---

## 🎉 使用说明

1. **注册账号** → http://localhost:5000/auth/register
2. **登录系统** → http://localhost:5000/auth/login
3. **新建查询** → 仪表盘输入关键词和选择平台
4. **查看结果** → 等待分析完成，查看详情
5. **下载报告** → 点击"下载报告"按钮

---

**项目创建时间**: 2026-06-17  
**状态**: ✅ 完成，可投入使用
