FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（Playwright 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxcb1 libxkbcommon0 libx11-6 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web_app/requirements.txt web_app_req.txt
RUN pip install --no-cache-dir -r web_app_req.txt

# 安装 Playwright 浏览器
RUN playwright install chromium && playwright install-deps chromium

# 复制项目
COPY . .

# 创建必要目录
RUN mkdir -p web_app/music web_app/uploads web_app/reports web_app/sqlite

EXPOSE 5000

CMD ["python", "web_app/app.py"]
