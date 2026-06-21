import os
import sys

from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_required, current_user
from flask_cors import CORS
from flask_socketio import SocketIO
from sqlalchemy import text

from config import Config
from models import db, User

# 创建 Flask 应用
app = Flask(__name__)
app.config.from_object(Config)

# 初始化扩展
db.init_app(app)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = '请先登录'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# 确保必要的目录存在
def create_directories():
    """创建必要的目录"""
    directories = [
        app.config['UPLOAD_FOLDER'],
        app.config['REPORT_FOLDER'],
        app.config['SQLITE_FOLDER']
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def ensure_query_history_columns():
    """Add new query options to existing SQLite databases."""
    columns = {
        row[1] for row in db.session.execute(text("PRAGMA table_info(query_history)")).fetchall()
    }
    additions = {
        "location": "VARCHAR(100) DEFAULT ''",
        "sample_count": "INTEGER DEFAULT 50",
        "sort_order": "VARCHAR(20) DEFAULT 'none'",
        "estimated_total": "INTEGER DEFAULT 0",
        "crawl_progress": "VARCHAR(50) DEFAULT ''",
    }
    for column, ddl in additions.items():
        if column not in columns:
            db.session.execute(text(f"ALTER TABLE query_history ADD COLUMN {column} {ddl}"))
    db.session.commit()


def safe_print(message: str = "") -> None:
    text_value = str(message)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        print(text_value)
    except UnicodeEncodeError:
        fallback = text_value.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(fallback)


# 注册蓝图
from api.auth import auth_bp
from api.routes import api_bp
from admin.routes import admin_bp

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/admin')


# 主页路由
@app.route('/')
def index():
    """首页"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/dashboard')
@login_required
def dashboard():
    """用户仪表盘"""
    return render_template('dashboard.html')


@app.route('/music')
@login_required
def music():
    """音乐搜索"""
    return render_template('music.html')


@app.route('/history')
@login_required
def history():
    """查询历史"""
    return render_template('history.html')


@app.route('/result/<int:query_id>')
@login_required
def result(query_id):
    """查看结果详情"""
    return render_template('result.html', query_id=query_id)


# 错误处理
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


# 初始化数据库
with app.app_context():
    create_directories()
    db.create_all()
    ensure_query_history_columns()
    safe_print("[OK] 数据库初始化成功")


if __name__ == '__main__':
    safe_print("=" * 60)
    safe_print("Multi-Agent 购物调研系统 - Web 版")
    safe_print("=" * 60)
    safe_print("访问地址: http://localhost:5000")
    safe_print(f"数据库: {app.config['SQLALCHEMY_DATABASE_URI']}")
    safe_print("=" * 60)

    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
