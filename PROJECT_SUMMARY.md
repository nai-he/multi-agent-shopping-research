# Multi-Agent 购物调研系统 - 项目总结

## 📦 项目完成情况

### ✅ 已完成的模块

#### 1. 项目基础架构
- [x] 完整的目录结构
- [x] 配置文件系统（agent_config.json, platform_config.json, workflow_config.json）
- [x] 共享工具库（logger, api_client）
- [x] 数据模型（Product, Seller, Review）
- [x] 常量定义（关键词库）

#### 2. 四个子 Agent
- [x] **Agent 1: ScraperAgent（数据采集器）**
  - 支持平台选择（闲鱼、淘宝、京东、拼多多）
  - Mock 模式完整实现
  - 数据缓存机制
  
- [x] **Agent 2: ReviewAnalyzerAgent（评价分析器）**
  - 情感分析（正面/中性/负面）
  - 差评关键词提取（5大类）
  - 刷评检测
  - 风险等级评估
  
- [x] **Agent 3: PriceMonitorAgent（价格监控器）**
  - 价格对比分析
  - 性价比计算（综合排名）
  - SQLite 历史价格追踪
  - 价格预警（异常检测）
  
- [x] **Agent 4: ReportGeneratorAgent（报告生成器）**
  - Markdown 报告生成
  - 5种可视化图表：
    1. 价格对比柱状图
    2. 卖家信誉雷达图
    3. 情感分析饼图
    4. 性价比排名柱状图
    5. 平台价格箱线图

#### 3. 主协调器
- [x] **MultiAgentCoordinator**
  - 工作流程控制
  - Agent 调度（串行 + 并行）
  - 错误处理和重试
  - 日志记录

#### 4. 数据与测试
- [x] Mock 数据（闲鱼、淘宝各2个商品）
- [x] 测试脚本（test_system.py）
- [x] 命令行接口（main.py）

#### 5. 文档
- [x] 项目 README.md
- [x] 各 Agent 的 README.md
- [x] 依赖清单（requirements.txt）

---

## 📊 项目统计

| 项目 | 数量 |
|------|------|
| Python 文件 | 17+ |
| 配置文件 | 3 |
| Mock 数据文件 | 2 |
| Agent 数量 | 5 (1主+4子) |
| 图表类型 | 5+ |
| 代码行数 | 2000+ |

---

## 🚀 如何使用

### 1. 安装依赖
```bash
cd E:\agentlearn\design
pip install -r requirements.txt
```

### 2. 运行测试
```bash
python test_system.py
```

### 3. 执行查询
```bash
# 基本查询
python agents/multi-agent/main.py --query "iPhone 15 Pro"

# 指定平台
python agents/multi-agent/main.py --query "小米 14" --platforms xianyu taobao
```

### 4. 查看结果
- **报告**: `reports/shopping_report_*.md`
- **图表**: `reports/charts/*.png`
- **日志**: `logs/*.log`

---

## 🎯 核心特性

### Multi-Agent 协同
```
用户查询
    ↓
Coordinator 协调
    ↓
┌─────────────┬─────────────┐
│  Agent 1    │  获取数据   │
└─────────────┘             │
    ↓                       │
┌─────────────┬─────────────┤
│  Agent 2    │  分析评价   │ ← 并行执行
│  Agent 3    │  监控价格   │
└─────────────┴─────────────┘
    ↓
┌─────────────┬─────────────┐
│  Agent 4    │  生成报告   │
└─────────────┴─────────────┘
    ↓
Markdown + 图表
```

### 技术亮点

1. **模块化设计**：每个 Agent 独立开发和测试
2. **配置驱动**：通过 JSON 配置控制系统行为
3. **并行处理**：Agent 2 和 Agent 3 并行执行，提升效率
4. **数据持久化**：SQLite 存储历史价格
5. **可视化报告**：5+ 种专业图表
6. **智能分析**：情感分析、风险评估、性价比计算

---

## 📁 文件清单

### 核心代码
```
agents/multi-agent/coordinator.py       # 主协调器
agents/multi-agent/main.py              # CLI 入口
agents/scraper-agent/agent.py           # 数据采集
agents/review-analyzer-agent/agent.py   # 评价分析
agents/price-monitor-agent/agent.py     # 价格监控
agents/report-generator-agent/agent.py  # 报告生成
```

### 共享模块
```
shared/utils/logger.py                  # 日志工具
shared/utils/api_client.py              # Claude API 客户端
shared/models/product.py                # 数据模型
shared/constants/keywords.py            # 关键词库
```

### 配置文件
```
config/agent_config.json                # Agent 配置
config/platform_config.json             # 平台配置
config/workflow_config.json             # 工作流配置
```

### 数据文件
```
data/mock_data/xianyu_products.json     # 闲鱼 Mock 数据
data/mock_data/taobao_products.json     # 淘宝 Mock 数据
data/database/price_history.db          # 价格历史数据库
```

---

## 🔧 技术栈

- **语言**: Python 3.8+
- **HTTP**: requests
- **解析**: BeautifulSoup4, lxml
- **可视化**: matplotlib, seaborn
- **词云**: wordcloud
- **分词**: jieba
- **数据库**: SQLite3
- **AI**: Claude Opus 4.7 (via New API)

---


### 项目描述
> 基于 Python + Multi-Agent + Flask 构建电商调研系统，围绕“自然语言需求输入 -> AI 意图解析 -> 多平台抓取 -> 评论/价格分析 -> Markdown 报告生成”形成端到端闭环，并支持 Web 端异步查询、历史记录与结果展示。

### 技术亮点
- **Multi-Agent 协同架构**：设计并实现 1 个主协调器 + 4 个功能 Agent，拆分抓取、评价分析、价格监控和报告生成职责
- **AI 意图解析链路**：接入 LLM，对用户自然语言需求进行结构化解析，提取品类、预算、规格、偏好、排除项与搜索关键词，驱动后续抓取流程
- **并行处理与状态跟踪**：通过线程池并行执行评价分析和价格监控，并在 Web 端记录查询状态、抓取进度和历史结果
- **数据分析与可视化**：实现情感分析、刷评检测、性价比计算，并使用 matplotlib 生成 5+ 种图表
- **配置驱动设计**：支持通过 JSON 配置灵活控制平台启用状态、工作流顺序和抓取参数

### 工作成果
- 完成 2000+ 行 Python 代码，实现 CLI + Web 双入口
- 打通 AI 意图解析、关键词扩展、多平台抓取、价格分析和报告输出闭环
- 实现查询历史、结果持久化、价格历史存储与图表导出能力
- 支持 Mock 模式与真实抓取模式切换，便于演示和后续迭代

### 当前局限与下一步
- **真实抓取链路仍在治理中**：受反爬、页面结构波动、字段不统一等影响，真实抓取结果在稳定性、完整性和清洗质量上还有提升空间，更适合表述为“多平台抓取与数据治理原型”
- **AI 使用目前偏轻量**：当前 AI 主要用于意图解析、关键词扩展和结构化参数抽取，尚未深度接入抓取纠错、结果重排、报告总结等环节
- **评测体系待补强**：下一步计划引入 **Harness**，围绕意图解析准确率、关键词覆盖率、抓取成功率、结果质量和报告可用性建立自动化评测与回归机制

### 简历表述（可直接复用）
- 基于 Python、Flask 与 Multi-Agent 架构开发电商调研系统，完成用户需求输入、AI 意图解析、多平台抓取、评论/价格分析与 Markdown 报告输出的端到端闭环
- 使用 LLM 对中文购物需求进行结构化解析，提取品类、预算、规格和搜索关键词，提升商品检索的针对性与可扩展性
- 针对真实抓取中的反爬与脏数据问题，持续进行抓取容错、数据清洗和流程治理，并规划引入 Harness 建立 Prompt/Eval/Regression 评测闭环

---

## 🚧 未来优化方向

### 功能增强
- [ ] 实现真实爬虫模式（需解决反爬）
- [ ] 添加更多图表类型（散点图、热力图、词云图）
- [ ] 生成交互式 HTML 报告
- [ ] 定时监控和价格提醒功能
- [ ] 支持更多电商平台
- [ ] 引入 Harness，建立 AI 意图解析与结果质量的自动化评测回归机制

### 架构优化
- [ ] Agent 间 HTTP API 通信
- [ ] 消息队列支持（Kafka/RabbitMQ）
- [ ] Docker 容器化部署
- [ ] 分布式部署支持
- [ ] Web 界面开发

### 性能优化
- [ ] 增加 Redis 缓存层
- [ ] 优化数据库查询
- [ ] 实现增量更新
- [ ] 添加监控和告警

---

## ✅ 验收标准

### 功能验收
- [x] 能够从配置的平台获取商品数据
- [x] 能够分析商品评价并识别风险
- [x] 能够计算性价比并排名
- [x] 能够生成包含图表的 Markdown 报告
- [x] 命令行接口正常工作

### 代码质量
- [x] 代码结构清晰，模块化设计
- [x] 完整的错误处理和日志记录
- [x] 配置文件规范，易于修改
- [x] 完整的项目文档

### 可演示性
- [x] Mock 数据完整，可直接运行
- [x] 测试脚本验证系统正常
- [x] README 文档详细
- [x] 生成的报告美观专业

---

## 📞 问题排查

### 常见问题

#### 1. 导入错误
```python
ModuleNotFoundError: No module named 'xxx'
```
**解决**: 确保在项目根目录运行，或检查 sys.path

#### 2. API 调用失败
```
API Key 无效或已过期
```
**解决**: 检查 `config/agent_config.json` 中的 API Key

#### 3. 图表中文显示乱码
```
方框乱码
```
**解决**: 确保安装了中文字体（SimHei, Microsoft YaHei）

---

## 🎉 项目交付

### 交付物清单
1. ✅ 完整的源代码（17+ Python 文件）
2. ✅ 配置文件（3个JSON）
3. ✅ Mock 数据（2个平台）
4. ✅ 项目文档（README.md）
5. ✅ 测试脚本（test_system.py）
6. ✅ 依赖清单（requirements.txt）

### 项目状态
**🟢 已完成，可投入使用**

---

## 📝 更新日志

### v1.0.0 (2026-06-17)
- ✅ 初始版本发布
- ✅ 实现完整的 Multi-Agent 架构
- ✅ 支持 Mock 模式
- ✅ 生成 5 种可视化图表

---

**项目创建时间**: 2026-06-17
**最后更新**: 2026-06-17
**状态**: ✅ 完成
