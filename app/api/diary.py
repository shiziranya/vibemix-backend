from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import and_, func, extract

from ..extensions import db
from ..models.cocktail import Cocktail
from ..models.saved_cocktail import UserSavedCocktail
from ..models.share_card import ShareCard
from ..utils.errors import AppError
from ..utils.response import error, success

diary_bp = Blueprint("diary", __name__)


@diary_bp.errorhandler(AppError)
def handle_app_error(e: AppError):
    return error(e.code, e.message, e.http_status)


@diary_bp.route("/calendar", methods=["GET"])
@jwt_required()
def get_calendar():
    """
    GET /api/diary/calendar
    获取指定月份的日历数据，返回每天的卡片数量和缩略图

    Query 参数:
        year   int  必填，年份（如 2026）
        month  int  必填，月份（1-12）
    """
    user_id = uuid.UUID(get_jwt_identity())
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if not year or not month or month < 1 or month > 12:
        return error(4101, "year 和 month 参数必填且有效", 422)

    # 查询该月所有已完成的卡片
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    cards = (
        db.session.query(ShareCard)
        .filter(
            ShareCard.user_id == user_id,
            ShareCard.status == "done",
            ShareCard.created_at >= start_date,
            ShareCard.created_at < end_date,
        )
        .order_by(ShareCard.created_at)
        .all()
    )

    # 查询该月的今日酒单计划数据（用于计算完成度）
    planned_counts = {}
    try:
        planned_cards = (
            db.session.query(
                UserSavedCocktail.plan_date,
                func.count(UserSavedCocktail.id).label("count"),
            )
            .filter(
                UserSavedCocktail.user_id == user_id,
                UserSavedCocktail.is_in_today == True,
                UserSavedCocktail.plan_date >= start_date,
                UserSavedCocktail.plan_date < end_date,
            )
            .group_by(UserSavedCocktail.plan_date)
            .all()
        )
        planned_counts = {
            pc.plan_date.isoformat(): pc.count for pc in planned_cards
        }
    except Exception:
        pass

    # 按日期分组
    days_dict = {}
    for card in cards:
        day_str = card.created_at.date().isoformat()
        if day_str not in days_dict:
            days_dict[day_str] = {
                "date": day_str,
                "count": 0,
                "preview_images": [],
                "planned_count": planned_counts.get(day_str, 0),
                "completion_rate": 0.0,
            }
        days_dict[day_str]["count"] += 1
        if len(days_dict[day_str]["preview_images"]) < 3 and card.image_url:
            days_dict[day_str]["preview_images"].append(card.image_url)
    
    # 计算完成率
    for day_data in days_dict.values():
        if day_data["planned_count"] > 0:
            day_data["completion_rate"] = round(
                day_data["count"] / day_data["planned_count"], 2
            )
        elif day_data["count"] > 0:
            day_data["completion_rate"] = 1.0

    # 统计数据
    total_this_month = len(cards)
    total_all_time = (
        db.session.query(ShareCard)
        .filter(ShareCard.user_id == user_id, ShareCard.status == "done")
        .count()
    )

    return success(
        {
            "year": year,
            "month": month,
            "days": list(days_dict.values()),
            "stats": {
                "total_this_month": total_this_month,
                "total_all_time": total_all_time,
            },
        }
    )


@diary_bp.route("/date", methods=["GET"])
@jwt_required()
def get_date_detail():
    """
    GET /api/diary/date
    获取指定日期的所有卡片详情

    Query 参数:
        date  string  必填，日期格式 YYYY-MM-DD（如 2026-08-15）
    """
    user_id = uuid.UUID(get_jwt_identity())
    date_str = request.args.get("date", type=str)

    if not date_str:
        return error(4101, "date 参数必填", 422)

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return error(4101, "date 格式不正确，应为 YYYY-MM-DD", 422)

    # 查询该日期的计划数
    planned_count = 0
    try:
        planned_count = (
            db.session.query(UserSavedCocktail)
            .filter(
                UserSavedCocktail.user_id == user_id,
                UserSavedCocktail.is_in_today == True,
                UserSavedCocktail.plan_date == target_date,
            )
            .count()
        )
    except Exception:
        pass

    # 查询该日期的所有卡片
    next_date = target_date + timedelta(days=1)
    cards = (
        db.session.query(ShareCard, Cocktail)
        .join(Cocktail, ShareCard.cocktail_id == Cocktail.id, isouter=True)
        .filter(
            ShareCard.user_id == user_id,
            ShareCard.status == "done",
            ShareCard.created_at >= target_date,
            ShareCard.created_at < next_date,
        )
        .order_by(ShareCard.created_at.desc())
        .all()
    )

    cards_data = []
    for card, cocktail in cards:
        card_dict = {
            "card_id": str(card.id),
            "image_url": card.image_url,
            "created_at": card.created_at.isoformat() if card.created_at else None,
            "mood_caption": card.mood_caption,
            "cocktail_name": card.cocktail_name,
            "ai_poetic": card.ai_poetic,
            "cocktail": None,
        }
        
        if cocktail:
            card_dict["cocktail"] = {
                "id": cocktail.id,
                "name": cocktail.name,
                "name_zh": cocktail.name_zh,
                "abv_level": cocktail.abv_level,
            }
        
        cards_data.append(card_dict)

    # 计算完成率
    completed_count = len(cards_data)
    completion_rate = 0.0
    if planned_count > 0:
        completion_rate = round(completed_count / planned_count, 2)
    elif completed_count > 0:
        completion_rate = 1.0

    return success({
        "date": date_str,
        "planned": planned_count,
        "completed": completed_count,
        "completion_rate": completion_rate,
        "cards": cards_data,
    })


@diary_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    """
    GET /api/diary/stats
    获取用户的整体调酒统计数据
    """
    user_id = uuid.UUID(get_jwt_identity())

    # 总卡片数
    total_cards = (
        db.session.query(ShareCard)
        .filter(ShareCard.user_id == user_id, ShareCard.status == "done")
        .count()
    )

    # 总天数（去重日期）
    distinct_dates = (
        db.session.query(func.date(ShareCard.created_at))
        .filter(ShareCard.user_id == user_id, ShareCard.status == "done")
        .distinct()
        .count()
    )

    # 本月统计
    now = datetime.now()
    month_start = date(now.year, now.month, 1)
    if now.month == 12:
        month_end = date(now.year + 1, 1, 1)
    else:
        month_end = date(now.year, now.month + 1, 1)

    this_month = (
        db.session.query(ShareCard)
        .filter(
            ShareCard.user_id == user_id,
            ShareCard.status == "done",
            ShareCard.created_at >= month_start,
            ShareCard.created_at < month_end,
        )
        .count()
    )

    # 本周统计
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)

    this_week = (
        db.session.query(ShareCard)
        .filter(
            ShareCard.user_id == user_id,
            ShareCard.status == "done",
            ShareCard.created_at >= week_start,
            ShareCard.created_at < week_end,
        )
        .count()
    )

    # 最爱鸡尾酒（按卡片数量排序，取前5）
    favorite_cocktails_raw = (
        db.session.query(
            Cocktail.name_zh,
            Cocktail.name,
            func.count(ShareCard.id).label("count"),
        )
        .join(ShareCard, ShareCard.cocktail_id == Cocktail.id)
        .filter(ShareCard.user_id == user_id, ShareCard.status == "done")
        .group_by(Cocktail.id, Cocktail.name_zh, Cocktail.name)
        .order_by(func.count(ShareCard.id).desc())
        .limit(5)
        .all()
    )

    favorite_cocktails = [
        {"name_zh": name_zh or name, "count": count}
        for name_zh, name, count in favorite_cocktails_raw
    ]

    # 第一张卡片日期
    first_card = (
        db.session.query(ShareCard)
        .filter(ShareCard.user_id == user_id, ShareCard.status == "done")
        .order_by(ShareCard.created_at)
        .first()
    )
    first_card_date = (
        first_card.created_at.date().isoformat() if first_card else None
    )

    return success(
        {
            "total_cards": total_cards,
            "total_days": distinct_dates,
            "this_month": this_month,
            "this_week": this_week,
            "favorite_cocktails": favorite_cocktails,
            "first_card_date": first_card_date,
        }
    )
