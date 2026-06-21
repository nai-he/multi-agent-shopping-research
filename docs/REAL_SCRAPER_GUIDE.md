# 真实爬虫使用说明
## 环境要求

### 1. 安装 Chrome 浏览器
- 下载地址: https://www.google.com/chrome/

### 2. 安装 ChromeDriver

**方法1: 自动安装（推荐）**
```bash
pip install webdriver-manager
```

然后修改 `scrapers/base_scraper.py` 中的驱动初始化代码：
```python
from webdriver_manager.chrome import ChromeDriverManager

self.driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)
```

**方法2: 手动安装**
1. 检查 Chrome 版本：打开 Chrome -> 设置 -> 关于 Chrome
2. 下载对应版本的 ChromeDriver: https://chromedriver.chromium.org/downloads
3. 将 chromedriver.exe 放到系统 PATH 或项目目录

## 使用方式

### 模式切换

在 `config/platform_config.json` 中修改 `mode`:

```json
"scraper_settings": {
  "mode": "real",  // 真实爬虫模式
  // "mode": "mock",  // Mock 数据模式
  "max_products_per_platform": 50
}
```

### 运行系统

```bash
# 启动 Web 应用
cd web_app
python app.py
```

然后访问 http://localhost:5000，搜索任何关键词（iPhone、自行车、笔记本等），系统会自动爬取真实数据！

## 爬虫特性

✅ **动态搜索**: 搜索什么爬什么，不再是固定的 mock 数据
✅ **多平台支持**: 同时支持闲鱼和淘宝
✅ **反反爬**: 内置随机延时、User-Agent 轮换
✅ **自动翻页**: 最多爬取 5 页，约 50 个商品
✅ **容错处理**: 网络错误、元素定位失败自动跳过

## 注意事项

1. **首次运行较慢**: 需要启动 Chrome 浏览器
2. **网络要求**: 需要能访问淘宝/闲鱼
3. **反爬风险**: 频繁爬取可能触发验证码，建议合理控制频率
4. **数据完整性**: 部分商品信息（评价、销量等）可能无法完整获取

## 故障排查

### 问题1: Chrome 驱动初始化失败
```
RuntimeError: Chrome 驱动初始化失败
```

**解决方案**:
- 确保已安装 Chrome 浏览器
- 安装 webdriver-manager: `pip install webdriver-manager`
- 或手动下载 ChromeDriver

### 问题2: 未找到商品元素
```
第 1 页未找到商品元素
```

**解决方案**:
- 网页结构可能已更新，需要调整 CSS 选择器
- 检查是否触发了验证码
- 尝试降低爬取频率,闲鱼短时间内访问多次会遭遇的风控

### 问题3: 爬取速度慢
**解决方案**:
- 调整 `headless=True` 使用无头模式
- 减少 `max_products_per_platform` 数量
- 使用 mock 模式进行开发调试

