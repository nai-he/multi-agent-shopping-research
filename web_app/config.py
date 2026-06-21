"""配置管理"""
import os
from pathlib import Path
from dotenv import load_dotenv
import sys

# 加载 .env 文件
basedir = Path(__file__).parent
project_root = basedir.parent
# 从项目根目录加载 .env
load_dotenv(project_root / '.env')
sys.path.insert(0, str(project_root))

from shared.utils.config_loader import load_claude_code_env

claude_code_env = load_claude_code_env()


class Config:
    """应用配置"""

    # Flask 基础配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{basedir / os.getenv('DATABASE_PATH', 'sqlite/shopping_web.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Claude API 配置
    CLAUDE_API_KEY = (
        os.getenv('CLAUDE_API_KEY')
        or claude_code_env.get('ANTHROPIC_AUTH_TOKEN')
        or claude_code_env.get('ANTHROPIC_API_KEY')
    )
    CLAUDE_API_BASE_URL = os.getenv('CLAUDE_API_BASE_URL') or claude_code_env.get('ANTHROPIC_BASE_URL')
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL') or claude_code_env.get('ANTHROPIC_MODEL') or 'claude-opus-4-7'

    # Session 配置
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.getenv('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')

    # 任务配置
    MAX_CONCURRENT_TASKS = int(os.getenv('MAX_CONCURRENT_TASKS', 3))
    TASK_TIMEOUT = int(os.getenv('TASK_TIMEOUT', 300))
    CACHE_TTL = int(os.getenv('CACHE_TTL', 3600))

    # 文件路径
    UPLOAD_FOLDER = basedir / 'uploads'
    REPORT_FOLDER = basedir / 'reports'
    SQLITE_FOLDER = basedir / 'sqlite'

    # 项目根目录（Multi-Agent 系统）
    PROJECT_ROOT = project_root

    # 音乐网关 API 配置
    MUSIC_GATEWAY_API_KEY = os.getenv('MUSIC_GATEWAY_API_KEY', '')
    MUSIC_GATEWAY_BASE_URL = os.getenv('MUSIC_GATEWAY_BASE_URL', 'https://gateway.karpov.cn/api')
