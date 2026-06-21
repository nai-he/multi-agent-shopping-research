"""数据库模型"""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def _serialize_utc(dt: datetime):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


class User(UserMixin, db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # 关系
    queries = db.relationship('QueryHistory', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class QueryHistory(db.Model):
    """查询历史模型"""
    __tablename__ = 'query_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    query = db.Column(db.String(200), nullable=False)
    platforms = db.Column(db.String(100))  # 逗号分隔的平台列表
    location = db.Column(db.String(100), default='')
    sample_count = db.Column(db.Integer, default=50)
    sort_order = db.Column(db.String(20), default='none')
    estimated_total = db.Column(db.Integer, default=0)
    crawl_progress = db.Column(db.String(50), default='')
    products_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    report_path = db.Column(db.String(500))
    error_message = db.Column(db.Text)
    elapsed_time = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime)

    # 结果数据（JSON）
    result_data = db.Column(db.Text)  # 存储 JSON 字符串

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'query': self.query,
            'platforms': self.platforms.split(',') if self.platforms else [],
            'location': self.location,
            'sample_count': self.sample_count,
            'sort_order': self.sort_order,
            'estimated_total': self.estimated_total,
            'crawl_progress': self.crawl_progress,
            'products_count': self.products_count,
            'status': self.status,
            'report_path': self.report_path,
            'error_message': self.error_message,
            'elapsed_time': self.elapsed_time,
            'created_at': _serialize_utc(self.created_at),
            'completed_at': _serialize_utc(self.completed_at)
        }

    def __repr__(self):
        return f'<QueryHistory {self.id}: {self.query}>'


class PriceAlert(db.Model):
    """价格提醒模型（可选功能）"""
    __tablename__ = 'price_alerts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    target_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime)

    def __repr__(self):
        return f'<PriceAlert {self.product_name}: ¥{self.target_price}>'
