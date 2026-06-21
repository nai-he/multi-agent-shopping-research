"""管理员后台路由。"""
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func

from models import db, QueryHistory, User

admin_bp = Blueprint("admin", __name__)

ADMIN_USERNAME = "root"
ADMIN_PASSWORD = "root"


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin.login"))
        return view_func(*args, **kwargs)

    return wrapper


def _build_user_summary(user: User) -> dict:
    recent_query = (
        db.session.query(QueryHistory)
        .filter_by(user_id=user.id)
        .order_by(QueryHistory.created_at.desc())
        .first()
    )

    total_queries = db.session.query(func.count(QueryHistory.id)).filter_by(user_id=user.id).scalar() or 0
    completed_queries = (
        db.session.query(func.count(QueryHistory.id))
        .filter_by(user_id=user.id, status="completed")
        .scalar()
        or 0
    )
    failed_queries = (
        db.session.query(func.count(QueryHistory.id))
        .filter_by(user_id=user.id, status="failed")
        .scalar()
        or 0
    )

    last_activity = recent_query.created_at if recent_query else user.last_login or user.created_at
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at,
        "last_login": user.last_login,
        "last_activity": last_activity,
        "total_queries": total_queries,
        "completed_queries": completed_queries,
        "failed_queries": failed_queries,
        "latest_query": recent_query.query if recent_query else "",
        "latest_status": recent_query.status if recent_query else "",
        "latest_location": recent_query.location if recent_query else "",
        "latest_sample_count": recent_query.sample_count if recent_query else 0,
    }


def _build_operation_summary(item: QueryHistory) -> dict:
    return {
        "id": item.id,
        "query": item.query,
        "platforms": item.platforms.split(",") if item.platforms else [],
        "location": item.location or "不限",
        "sample_count": item.sample_count or 0,
        "sort_order": item.sort_order or "none",
        "status": item.status,
        "products_count": item.products_count or 0,
        "estimated_total": item.estimated_total or 0,
        "crawl_progress": item.crawl_progress or "",
        "elapsed_time": item.elapsed_time,
        "error_message": item.error_message,
        "created_at": item.created_at,
        "completed_at": item.completed_at,
        "user": {
            "id": item.user.id if item.user else None,
            "username": item.user.username if item.user else "未知用户",
            "email": item.user.email if item.user else "",
        },
    }


@admin_bp.route("/")
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)

    stats = {
        "users_total": db.session.query(func.count(User.id)).scalar() or 0,
        "queries_total": db.session.query(func.count(QueryHistory.id)).scalar() or 0,
        "completed_total": db.session.query(func.count(QueryHistory.id)).filter_by(status="completed").scalar() or 0,
        "failed_total": db.session.query(func.count(QueryHistory.id)).filter_by(status="failed").scalar() or 0,
        "processing_total": db.session.query(func.count(QueryHistory.id)).filter_by(status="processing").scalar() or 0,
        "active_users_24h": (
            db.session.query(func.count(User.id))
            .filter(User.last_login.isnot(None), User.last_login >= day_ago)
            .scalar()
            or 0
        ),
    }

    users = (
        db.session.query(User)
        .order_by(User.last_login.desc().nullslast(), User.created_at.desc())
        .all()
    )
    recent_users = [_build_user_summary(user) for user in users[:8]]

    recent_operations = (
        db.session.query(QueryHistory)
        .order_by(QueryHistory.created_at.desc())
        .limit(10)
        .all()
    )
    recent_operations = [_build_operation_summary(item) for item in recent_operations]

    recent_failures = (
        db.session.query(QueryHistory)
        .filter_by(status="failed")
        .order_by(QueryHistory.created_at.desc())
        .limit(5)
        .all()
    )
    recent_failures = [_build_operation_summary(item) for item in recent_failures]

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_users=recent_users,
        recent_operations=recent_operations,
        recent_failures=recent_failures,
    )


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_authenticated"] = True
            session["admin_username"] = ADMIN_USERNAME
            session["admin_login_at"] = datetime.utcnow().isoformat()
            flash("管理员登录成功", "success")
            return redirect(url_for("admin.dashboard"))

        flash("账号或密码错误", "danger")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("admin_authenticated", None)
    session.pop("admin_username", None)
    session.pop("admin_login_at", None)
    flash("管理员已退出登录", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/users")
@admin_required
def users():
    users = (
        db.session.query(User)
        .order_by(User.created_at.desc())
        .all()
    )
    summaries = [_build_user_summary(user) for user in users]
    return render_template("admin/users.html", users=summaries)


@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        return render_template("404.html"), 404

    summary = _build_user_summary(user)
    recent_queries = (
        db.session.query(QueryHistory)
        .filter_by(user_id=user.id)
        .order_by(QueryHistory.created_at.desc())
        .limit(20)
        .all()
    )
    operations = [_build_operation_summary(item) for item in recent_queries]

    return render_template(
        "admin/user_detail.html",
        user=summary,
        operations=operations,
    )


@admin_bp.route("/operations")
@admin_required
def operations():
    page = request.args.get("page", 1, type=int)
    per_page = 15
    pagination = (
        db.session.query(QueryHistory)
        .order_by(QueryHistory.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    items = [_build_operation_summary(item) for item in pagination.items]
    return render_template(
        "admin/operations.html",
        operations=items,
        pagination=pagination,
    )
