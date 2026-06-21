"""用户认证路由"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, User, QueryHistory
from datetime import datetime

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)

        user = db.session.query(User).filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()

            flash('登录成功！', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """注册"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # 验证
        if not username or not email or not password:
            flash('请填写所有字段', 'danger')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('两次密码不一致', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('密码长度至少6位', 'danger')
            return render_template('auth/register.html')

        # 检查用户名是否已存在
        if db.session.query(User).filter_by(username=username).first():
            flash('用户名已存在', 'danger')
            return render_template('auth/register.html')

        # 检查邮箱是否已存在
        if db.session.query(User).filter_by(email=email).first():
            flash('邮箱已被注册', 'danger')
            return render_template('auth/register.html')

        # 创建新用户
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('注册成功！请登录', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """登出"""
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('index'))


@auth_bp.route('/profile')
@login_required
def profile():
    """个人资料"""
    recent_queries = (
        db.session.query(QueryHistory)
        .filter_by(user_id=current_user.id)
        .order_by(QueryHistory.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        'auth/profile.html',
        recent_queries=recent_queries,
        total_queries=current_user.queries.count(),
        completed_queries=current_user.queries.filter_by(status='completed').count(),
        failed_queries=current_user.queries.filter_by(status='failed').count(),
        processing_queries=current_user.queries.filter_by(status='processing').count(),
    )
