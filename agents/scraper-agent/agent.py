"""数据采集 Agent - ScraperAgent"""
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

agent_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(agent_dir))

from shared.models.product import Product, Review, Seller
from shared.utils.api_client import ClaudeAPIClient
from shared.utils.config_loader import load_agent_config
from shared.utils.logger import AgentLogger

try:
    from live_scrapers import (
        JDLiveScraper,
        PDDLiveScraper,
        TaobaoLiveScraper,
        XianyuLiveScraper,
        XianyuScrapeBlocked,
    )
except Exception:
    JDLiveScraper = None
    PDDLiveScraper = None
    TaobaoLiveScraper = None
    XianyuLiveScraper = None
    XianyuScrapeBlocked = RuntimeError


class ScraperAgent:
    """数据采集器 Agent"""

    REAL_MODE_MAX_QUERY_CANDIDATES = 4

    QUERY_EXPANSIONS = {
        "自行车": ["自行车", "单车", "骑行", "山地车", "公路车", "折叠车", "通勤车", "变速车"],
        "手机": ["手机", "iphone", "小米", "华为", "荣耀", "oppo", "vivo", "一加"],
        "笔记本": ["笔记本", "电脑", "macbook", "thinkpad", "游戏本", "轻薄本"],
        "耳机": ["耳机", "airpods", "蓝牙耳机", "降噪耳机"],
        "相机": ["相机", "微单", "单反", "镜头"],
        "运动鞋": ["运动鞋", "跑鞋", "球鞋", "板鞋", "篮球鞋"],
    }

    FUJIAN_LOCATIONS = [
        "福建",
        "福州",
        "厦门",
        "泉州",
        "漳州",
        "莆田",
        "三明",
        "南平",
        "龙岩",
        "宁德",
        "平潭",
    ]

    CITY_TO_PROVINCE = {
        # 福建
        "福州": "福建", "厦门": "福建", "泉州": "福建", "漳州": "福建",
        "莆田": "福建", "三明": "福建", "南平": "福建", "龙岩": "福建",
        "宁德": "福建", "平潭": "福建",
        # 广东
        "广州": "广东", "深圳": "广东", "东莞": "广东", "佛山": "广东",
        "珠海": "广东", "中山": "广东", "惠州": "广东", "汕头": "广东",
        # 浙江
        "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "嘉兴": "浙江",
        "湖州": "浙江", "绍兴": "浙江", "金华": "浙江", "台州": "浙江",
        # 江苏
        "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏",
        "南通": "江苏", "扬州": "江苏", "徐州": "江苏",
        # 山东
        "济南": "山东", "青岛": "山东", "烟台": "山东", "威海": "山东",
        "潍坊": "山东", "临沂": "山东",
        # 其他省会/直辖市
        "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
        "成都": "四川", "武汉": "湖北", "长沙": "湖南", "郑州": "河南",
        "西安": "陕西", "合肥": "安徽", "南昌": "江西", "沈阳": "辽宁",
        "大连": "辽宁", "哈尔滨": "黑龙江", "长春": "吉林", "昆明": "云南",
        "贵阳": "贵州", "南宁": "广西", "海口": "海南", "石家庄": "河北",
        "太原": "山西", "呼和浩特": "内蒙古", "乌鲁木齐": "新疆",
        "兰州": "甘肃", "西宁": "青海", "银川": "宁夏", "拉萨": "西藏",
    }

    def __init__(self, config_path: str = None):
        self.logger = AgentLogger("ScraperAgent", log_dir=str(project_root / "logs"))
        self.logger.info("初始化 ScraperAgent...")

        if config_path is None:
            config_path = project_root / "config" / "agent_config.json"

        agent_config = load_agent_config(config_path)
        platform_config_path = project_root / "config" / "platform_config.json"
        with open(platform_config_path, "r", encoding="utf-8-sig") as f:
            self.platform_config = json.load(f)

        api_config = agent_config["api"]
        self.api_client = ClaudeAPIClient(
            api_key=api_config["api_key"],
            base_url=api_config["base_url"],
            model=api_config["model"],
        )

        self.mode = self.platform_config["scraper_settings"]["mode"]
        self.max_products_per_platform = self.platform_config["scraper_settings"].get(
            "max_products_per_platform",
            50,
        )
        self.headless = bool(
            self.platform_config["scraper_settings"].get("headless", True)
        )
        self.wait_after_load_ms = int(
            self.platform_config["scraper_settings"].get("wait_after_load_ms", 1800)
        )
        self.mock_data_dir = project_root / "data" / "mock_data"
        self.last_crawl_meta: Dict[str, Any] = {}

        self.logger.info(
            f"ScraperAgent 初始化完成，模式: {self.mode}, headless: {self.headless}"
        )

    def fetch_products(
        self,
        query: str,
        platforms: List[str] = None,
        max_results_per_platform: int = None,
        location: str = "",
        sort_order: str = "none",
        search_keywords: List[str] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        category: str = "",
        sub_category: str = "",
        progress_callback=None,
    ) -> List[Product]:
        self.logger.info(
            f"开始抓取商品: {query}, 平台: {platforms}, 地区: {location}, 排序: {sort_order}"
        )
        if search_keywords:
            self.logger.info(f"AI 扩展关键词: {search_keywords}")
        if category or sub_category:
            self.logger.info(f"品类: {category or '未知'} / {sub_category or '未细分'}")

        if platforms is None:
            platforms = [
                name for name, config in self.platform_config["platforms"].items()
                if config["enabled"]
            ]

        limit = max_results_per_platform or self.max_products_per_platform
        resolved_budget_min, resolved_budget_max = self._resolve_budget_range(
            query=query,
            budget_min=budget_min,
            budget_max=budget_max,
        )
        if resolved_budget_min is not None or resolved_budget_max is not None:
            self.logger.info(
                f"预算过滤: min={resolved_budget_min if resolved_budget_min is not None else '-'}, "
                f"max={resolved_budget_max if resolved_budget_max is not None else '-'}"
            )

        all_products = []
        platform_errors = []
        self.last_crawl_meta = {
            "estimated_total": 0,
            "target_count": limit,
            "crawled_count": 0,
            "progress_text": f"0/{limit}",
            "location": location,
            "sort_order": sort_order,
            "budget_min": resolved_budget_min,
            "budget_max": resolved_budget_max,
            "platforms": {},
            "platform_errors": [],
            "underfilled": False,
            "underfilled_by": 0,
            "status_message": "",
        }

        search_plan = self._build_search_plan(
            query=query,
            search_keywords=search_keywords,
            category=category,
            sub_category=sub_category,
        )
        keywords_to_search = (
            search_plan["live_queries"]
            if self.mode == "real"
            else search_plan["all_queries"]
        )
        ranking_query = search_plan.get("core_query") or query
        self.last_crawl_meta["query_plan"] = search_plan
        self.logger.info(f"实际搜索词: {keywords_to_search}")

        for platform in platforms:
            self.logger.info(f"正在从 {platform} 抓取数据...")
            try:
                platform_products = []
                platform_attempts = []
                platform_requires_login = False
                platform_risk_detected = False
                platform_blocked_messages: List[str] = []
                platform_estimated_total = 0
                platform_successful_query = ""
                latest_platform_meta: Dict[str, Any] = {}

                for index, kw in enumerate(keywords_to_search):
                    if not kw:
                        continue
                    remaining_target = max(1, limit - len(platform_products))
                    if self.mode == "real":
                        kw_limit = remaining_target
                    else:
                        remaining_keywords = max(1, len(keywords_to_search) - index)
                        kw_limit = remaining_target if remaining_keywords == 1 else max(
                            1,
                            math.ceil(remaining_target / remaining_keywords),
                        )
                    if self.mode == "mock":
                        products = self._load_mock_data(
                            platform,
                            kw,
                            kw_limit,
                            location=location,
                            sort_order=sort_order,
                        )
                    else:
                        real_location = self.CITY_TO_PROVINCE.get(location, location)
                        products = self._scrape_real_data(
                            platform, kw, kw_limit,
                            location=real_location,
                            sort_order=sort_order,
                            budget_min=resolved_budget_min,
                            budget_max=resolved_budget_max,
                            progress_callback=progress_callback,
                        )
                    attempt_meta = dict(
                        self.last_crawl_meta.get("platforms", {}).get(platform, {}) or {}
                    )
                    latest_platform_meta = attempt_meta or latest_platform_meta
                    products = self._rank_products_for_query(products, kw)
                    products = [
                        p for p in products
                        if self._matches_budget(p.price, resolved_budget_min, resolved_budget_max)
                    ]
                    attempt_summary = self._build_query_attempt(
                        query=kw,
                        requested_limit=kw_limit,
                        returned_count=len(products),
                        platform_meta=attempt_meta,
                    )
                    platform_attempts.append(attempt_summary)
                    platform_estimated_total = max(
                        platform_estimated_total,
                        int(attempt_meta.get("estimated_total", 0) or 0),
                    )
                    platform_requires_login = (
                        platform_requires_login
                        or bool(attempt_meta.get("requires_login"))
                    )
                    platform_risk_detected = (
                        platform_risk_detected
                        or bool(attempt_meta.get("risk_detected"))
                    )
                    for blocked_message in attempt_summary.get("blocked_messages", []):
                        if blocked_message not in platform_blocked_messages:
                            platform_blocked_messages.append(blocked_message)
                    if products and not platform_successful_query:
                        platform_successful_query = kw
                    platform_products.extend(products)

                    platform_products = self._dedupe_products(platform_products)
                    platform_products = self._rank_products_for_query(
                        platform_products,
                        ranking_query,
                    )

                    if len(platform_products) >= limit:
                        break
                    if self.mode == "real" and self._should_stop_live_fallback(
                        attempt_meta=attempt_meta,
                        returned_count=len(products),
                        current_count=len(platform_products),
                        target_count=limit,
                    ):
                        break

                platform_meta = self._finalize_platform_meta(
                    platform=platform,
                    base_meta=latest_platform_meta,
                    target_count=limit,
                    actual_count=len(platform_products[:limit]),
                    queries_planned=keywords_to_search,
                    query_attempts=platform_attempts,
                    estimated_total=platform_estimated_total,
                    blocked_messages=platform_blocked_messages,
                    requires_login=platform_requires_login,
                    risk_detected=platform_risk_detected,
                    successful_query=platform_successful_query,
                )
                self.last_crawl_meta.setdefault("platforms", {})[platform] = platform_meta
                all_products.extend(platform_products[:limit])
                if platform_meta:
                    self.last_crawl_meta["estimated_total"] += platform_meta.get("estimated_total", 0)
                self.last_crawl_meta.setdefault("platform_success", []).append(platform)
                self.logger.info(f"从 {platform} 获取了 {len(platform_products[:limit])} 个商品")
            except Exception as e:
                error_message = str(e)
                blocked_messages = []
                if error_message:
                    blocked_messages.append(error_message)
                requires_login = any(token in error_message for token in ("登录", "login", "验证"))
                risk_detected = any(token in error_message for token in ("风控", "RGV587", "FAIL_SYS_USER_VALIDATE", "挤爆"))
                platform_errors.append({"platform": platform, "error": error_message})
                self.last_crawl_meta["platform_errors"].append(
                    {"platform": platform, "error": error_message}
                )
                self.last_crawl_meta.setdefault("platforms", {})[platform] = {
                    "error": error_message,
                    "estimated_total": 0,
                    "target_count": limit,
                    "crawled_count": 0,
                    "progress_text": f"0/{limit}",
                    "underfilled": True,
                    "underfilled_by": limit,
                    "queries_planned": list(keywords_to_search or []),
                    "query_attempts": [],
                    "query_mode": "sequential_fallback" if self.mode == "real" else "fanout_merge",
                    "query_used": "",
                    "successful_query": "",
                    "requires_login": requires_login,
                    "risk_detected": risk_detected,
                    "blocked_messages": blocked_messages,
                    "status_message": error_message,
                    "suggested_next_action": self._build_platform_next_action(platform, {
                        "requires_login": requires_login,
                        "risk_detected": risk_detected,
                        "blocked_messages": blocked_messages,
                        "status_message": error_message,
                        "crawled_count": 0,
                        "target_count": limit,
                    }),
                }
                self.logger.error(f"从 {platform} 抓取数据失败: {error_message}")

        self.logger.info(f"总共获取了 {len(all_products)} 个商品")
        all_products = self._sort_products(all_products, sort_order)
        self.last_crawl_meta["crawled_count"] = len(all_products)
        denominator = self.last_crawl_meta.get("estimated_total") or limit
        self.last_crawl_meta["progress_text"] = f"{len(all_products)}/{denominator}"
        self.last_crawl_meta["underfilled"] = len(all_products) < limit
        self.last_crawl_meta["underfilled_by"] = max(0, limit - len(all_products))

        status_messages = []
        for platform_name, platform_meta in self.last_crawl_meta.get("platforms", {}).items():
            if not isinstance(platform_meta, dict):
                continue
            message = platform_meta.get("status_message")
            if message:
                status_messages.append(f"{platform_name}: {message}")
        if status_messages:
            self.last_crawl_meta["status_message"] = " | ".join(status_messages)
        elif self.last_crawl_meta["underfilled"]:
            self.last_crawl_meta["status_message"] = f"目标 {limit} 个结果，当前只拿到 {len(all_products)} 个"

        if not all_products and platform_errors:
            error_text = "; ".join(
                f"{item['platform']}: {item['error']}" for item in platform_errors
            )
            self.last_crawl_meta["failure_reason"] = error_text
            self.logger.warning(f"所有平台均未抓取到商品：{error_text}")

        return all_products

    def _load_mock_data(
        self,
        platform: str,
        query: str,
        max_results: int = None,
        location: str = "",
        sort_order: str = "none",
        progress_callback=None,
    ) -> List[Product]:
        mock_file = self.mock_data_dir / f"{platform}_products.json"
        if not mock_file.exists():
            self.logger.warning(f"Mock 数据文件不存在: {mock_file}")
            return []

        with open(mock_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        scored_products = []
        for item in data:
            relevance_score = self._score_mock_item(item, query)
            if relevance_score <= 0:
                continue

            seller_data = item.get("seller")
            seller = Seller(**seller_data) if seller_data else None
            reviews_data = item.get("reviews", [])
            reviews = [Review(**review) for review in reviews_data]

            product = Product(
                product_id=item["product_id"],
                title=item["title"],
                price=item["price"],
                platform=item["platform"],
                url=item["url"],
                sales=item.get("sales", 0),
                stock=item.get("stock"),
                seller=seller,
                reviews=reviews,
                review_count=item.get("review_count", 0),
                positive_rate=item.get("positive_rate", 0.0),
                images=item.get("images", []),
                description=item.get("description", ""),
                tags=item.get("tags", []),
            )

            # mock 数据没有地区字段，跳过地区过滤
            # if location and location not in self._product_location_text(item, product):
            #     continue

            scored_products.append((relevance_score, product))

        total_matched = len(scored_products)

        scored_products.sort(
            key=lambda item: (
                -item[0],
                -item[1].sales,
                item[1].price,
                item[1].product_id,
            )
        )

        if max_results:
            scored_products = scored_products[:max_results]

        # 记录该平台的估算总数
        self.last_crawl_meta.setdefault("platforms", {})[platform] = {
            "estimated_total": total_matched,
            "crawled_count": len(scored_products),
        }

        products = [product for _, product in scored_products]
        return self._sort_products(products, sort_order)

    def _normalize_text(self, text: Any) -> str:
        return str(text or "").strip().lower()

    def _build_search_terms(self, query: str) -> List[str]:
        query_text = self._normalize_text(query)
        terms = set()

        if query_text:
            terms.add(query_text)

        terms.update(t for t in re.split(r"[\s,，/|+_-]+", query_text) if t)
        terms.update(re.findall(r"[a-z0-9]+", query_text))

        for key, aliases in self.QUERY_EXPANSIONS.items():
            alias_group = {self._normalize_text(key)}
            alias_group.update(self._normalize_text(alias) for alias in aliases)

            if any(alias and (alias in query_text or query_text in alias) for alias in alias_group):
                terms.update(alias_group)

        return [term for term in terms if term]

    def _score_mock_item(self, item: Dict[str, Any], query: str) -> int:
        title = self._normalize_text(item.get("title"))
        description = self._normalize_text(item.get("description"))
        tags = [self._normalize_text(tag) for tag in item.get("tags", [])]
        full_text = " ".join([title, description, *tags])

        query_text = self._normalize_text(query)
        search_terms = self._build_search_terms(query)
        query_tokens = [t for t in re.split(r"[\s,，/|+_-]+", query_text) if t]

        score = 0
        if query_text and query_text in title:
            score += 100
        elif query_text and query_text in full_text:
            score += 50

        if query_tokens and all(token in full_text for token in query_tokens):
            score += 30

        for term in search_terms:
            if term in title:
                score += 20
            if any(term in tag for tag in tags):
                score += 12
            if term in description:
                score += 6

        return score

    def _dedupe_products(self, products: List[Product]) -> List[Product]:
        seen_ids = set()
        deduped = []
        for product in products:
            if product.product_id in seen_ids:
                continue
            seen_ids.add(product.product_id)
            deduped.append(product)
        return deduped

    def _build_search_queries(
        self,
        query: str,
        search_keywords: Optional[List[str]] = None,
        category: str = "",
        sub_category: str = "",
    ) -> List[str]:
        candidates: List[str] = []

        if search_keywords:
            candidates.extend(search_keywords[:8])

        if sub_category:
            candidates.append(sub_category)
        if category:
            candidates.append(category)

        candidates.append(query)

        cleaned: List[str] = []
        seen = set()
        for candidate in candidates:
            normalized = self._sanitize_search_query_v4(candidate)
            if not normalized:
                continue
            if not self._is_meaningful_search_query(normalized):
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)

        return cleaned[:6]

    def _build_search_plan(
        self,
        query: str,
        search_keywords: Optional[List[str]] = None,
        category: str = "",
        sub_category: str = "",
    ) -> Dict[str, Any]:
        all_queries = self._build_search_queries(
            query=query,
            search_keywords=search_keywords,
            category=category,
            sub_category=sub_category,
        )
        core_query = self._extract_core_search_query(query)
        live_candidates: List[str] = []
        seen = set()

        def add_candidate(value: Any) -> None:
            normalized = self._sanitize_search_query_v4(value)
            if not normalized or not self._is_meaningful_search_query(normalized):
                return
            key = normalized.lower()
            if key in seen:
                return
            seen.add(key)
            live_candidates.append(normalized)

        for keyword in search_keywords or []:
            add_candidate(keyword)
        add_candidate(sub_category)
        add_candidate(core_query)
        add_candidate(category)

        if not live_candidates:
            add_candidate(query)
        if not all_queries:
            all_queries = live_candidates[:1] or [str(query or "").strip()]

        live_queries = live_candidates[:self.REAL_MODE_MAX_QUERY_CANDIDATES] or all_queries[:1]
        if not live_queries:
            live_queries = [str(query or "").strip()]

        return {
            "mode": "sequential_fallback" if self.mode == "real" else "fanout_merge",
            "original_query": str(query or "").strip(),
            "core_query": core_query,
            "all_queries": all_queries[:6],
            "live_queries": live_queries,
            "category": category or "",
            "sub_category": sub_category or "",
            "search_keywords": list(search_keywords or []),
        }

    def _build_query_attempt(
        self,
        query: str,
        requested_limit: int,
        returned_count: int,
        platform_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        meta = dict(platform_meta or {})
        return {
            "query": query,
            "requested_limit": requested_limit,
            "returned_count": returned_count,
            "estimated_total": int(meta.get("estimated_total", 0) or 0),
            "status_message": meta.get("status_message", "") or "",
            "blocked_messages": list(meta.get("blocked_messages") or []),
            "requires_login": bool(meta.get("requires_login")),
            "risk_detected": bool(meta.get("risk_detected")),
            "final_url": meta.get("final_url", "") or "",
        }

    def _should_stop_live_fallback(
        self,
        attempt_meta: Optional[Dict[str, Any]],
        returned_count: int,
        current_count: int,
        target_count: int,
    ) -> bool:
        meta = dict(attempt_meta or {})
        if current_count >= target_count:
            return True
        if meta.get("requires_login") or meta.get("risk_detected"):
            return True
        status_message = str(meta.get("status_message") or "")
        blocked_messages = meta.get("blocked_messages") or []
        if blocked_messages:
            return True
        if returned_count <= 0 and any(
            token in status_message for token in ("登录", "验证", "风控", "403", "RGV587")
        ):
            return True
        return False

    def _build_platform_next_action(self, platform: str, meta: Dict[str, Any]) -> str:
        if meta.get("requires_login"):
            return (
                f"先运行 scripts/bootstrap_marketplace_session.py --platform {platform} "
                f"完成一次手动登录，再复用 data/browser_profiles/{platform} 会话重试"
            )
        if meta.get("risk_detected"):
            return (
                f"{platform} 当前匿名会话已触发风控，建议改用已登录持久化会话，"
                "或等待一段时间后降低频率重试"
            )
        if meta.get("underfilled"):
            return "可尝试更具体的关键词，或切换更多平台补足样本"
        return ""

    def _finalize_platform_meta(
        self,
        platform: str,
        base_meta: Optional[Dict[str, Any]],
        target_count: int,
        actual_count: int,
        queries_planned: List[str],
        query_attempts: List[Dict[str, Any]],
        estimated_total: int,
        blocked_messages: List[str],
        requires_login: bool,
        risk_detected: bool,
        successful_query: str,
    ) -> Dict[str, Any]:
        meta = dict(base_meta or {})
        meta["estimated_total"] = max(
            int(meta.get("estimated_total", 0) or 0),
            int(estimated_total or 0),
            actual_count,
        )
        meta["target_count"] = target_count
        meta["crawled_count"] = actual_count
        meta["progress_text"] = f"{actual_count}/{meta['estimated_total'] or target_count}"
        meta["underfilled"] = actual_count < target_count
        meta["underfilled_by"] = max(0, target_count - actual_count)
        meta["queries_planned"] = list(queries_planned or [])
        meta["query_attempts"] = list(query_attempts or [])
        meta["query_mode"] = "sequential_fallback" if self.mode == "real" else "fanout_merge"
        meta["query_used"] = successful_query or (
            query_attempts[0]["query"] if query_attempts else ""
        )
        meta["successful_query"] = successful_query or ""
        meta["requires_login"] = bool(meta.get("requires_login") or requires_login)
        meta["risk_detected"] = bool(meta.get("risk_detected") or risk_detected)

        merged_blocked_messages = list(meta.get("blocked_messages") or [])
        for blocked_message in blocked_messages:
            if blocked_message not in merged_blocked_messages:
                merged_blocked_messages.append(blocked_message)
        meta["blocked_messages"] = merged_blocked_messages

        if query_attempts:
            meta["final_url"] = query_attempts[-1].get("final_url") or meta.get("final_url", "")
        if not meta.get("status_message"):
            latest_status = next(
                (
                    attempt.get("status_message")
                    for attempt in reversed(query_attempts)
                    if attempt.get("status_message")
                ),
                "",
            )
            meta["status_message"] = latest_status
        meta["suggested_next_action"] = self._build_platform_next_action(platform, meta)
        return meta

    def _sanitize_search_query(self, text: Any) -> str:
        cleaned = str(text or "")
        cleaned = re.sub(
            r"(?:预算|大概|大约|差不多|想买|求购|求|帮我找|帮我搜|看看|有没有)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"(?:不超过|低于|高于|大于|小于|至少|不到)\s*\d+(?:\.\d+)?\s*(?:元|块|￥|¥)?",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\d+(?:\.\d+)?\s*(?:元|块|￥|¥)?\s*(?:以下|以内|以上|左右|起|出头)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\d+(?:\.\d+)?\s*(?:元|块|￥|¥)?\s*(?:-|到|至|~|—)\s*\d+(?:\.\d+)?\s*(?:元|块|￥|¥)?",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\b(?:的|款|左右|以内|以下|以上|一下|一个|一双|那种)\b", " ", cleaned)
        cleaned = re.sub(r"\d+(?:\.\d+)?", " ", cleaned)
        cleaned = re.sub(r"[，,。.!！？?；;]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _extract_core_search_query(self, query: str) -> str:
        sanitized = self._sanitize_search_query_v4(query)
        if sanitized and self._is_meaningful_search_query(sanitized):
            return sanitized
        return str(query or "").strip()

    def _is_meaningful_search_query(self, query: str) -> bool:
        normalized = str(query or "").strip()
        if not normalized:
            return False
        return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", normalized))

    def _resolve_budget_range(
        self,
        query: str,
        budget_min: Optional[float],
        budget_max: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        resolved_min = self._normalize_budget_value(budget_min)
        resolved_max = self._normalize_budget_value(budget_max)

        if resolved_min is not None or resolved_max is not None:
            return resolved_min, resolved_max

        return self._parse_budget_from_text_v3(query)

    def _normalize_budget_value(self, value: Any) -> Optional[float]:
        if value in (None, "", False):
            return None
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            return None
        return normalized if normalized >= 0 else None

    def _sanitize_search_query_v2(self, text: Any) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return ""

        filler_patterns = [
            r"(帮我|帮忙|想买|求购|看看|推荐一下|推荐|预算|大概|大约|左右的?)",
            r"(有没有|来个|整一个|那种|这种|求推荐)",
        ]
        for pattern in filler_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        budget_patterns = [
            r"(不超过|低于|不到|小于|至多|最高)\s*\d+(?:\.\d+)?\s*(?:元|块|rmb)?",
            r"\d+(?:\.\d+)?\s*(?:元|块|rmb)?\s*(以下|以内|之内)",
            r"(高于|大于|不少于|至少|最低)\s*\d+(?:\.\d+)?\s*(?:元|块|rmb)?",
            r"\d+(?:\.\d+)?\s*(?:元|块|rmb)?\s*(以上)",
            r"\d+(?:\.\d+)?\s*(?:元|块|rmb)?\s*(到|至|\-|~|—)\s*\d+(?:\.\d+)?\s*(?:元|块|rmb)?",
        ]
        for pattern in budget_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r"(的|以内|以下|以上|左右)", " ", cleaned)
        cleaned = re.sub(r"[，。！？、,:;；]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _sanitize_search_query_v3(self, text: Any) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return ""

        filler_patterns = [
            r"(帮我|帮忙|想买|求购|看看|推荐一下|推荐|预算|大概|大约)",
            r"(有没有|来个|整一个|那种|这种|求推荐)",
        ]
        for pattern in filler_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        budget_patterns = [
            r"(不超过|低于|不到|小于|至多|最高)\s*\d+(?:\.\d+)?\s*(?:元|块|rmb)?",
            r"\d+(?:\.\d+)?\s*(?:元|块|rmb)?\s*(以下|以内|之内)",
            r"(高于|大于|不少于|至少|最低)\s*\d+(?:\.\d+)?\s*(?:元|块|rmb)?",
            r"\d+(?:\.\d+)?\s*(?:元|块|rmb)?\s*(以上)",
            r"\d+(?:\.\d+)?\s*(?:元|块|rmb)?\s*(到|至|\-|~|—)\s*\d+(?:\.\d+)?\s*(?:元|块|rmb)?",
        ]
        for pattern in budget_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r"\b(的|以内|以下|以上|左右)\b", " ", cleaned)
        cleaned = re.sub(r"[，。！？、,:;；]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _sanitize_search_query_v4(self, text: Any) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return ""

        filler_patterns = [
            r"(帮我|帮忙|想买|求购|看看|推荐一下|推荐|预算|大概|大约|有没有|来个|这种|那种)",
        ]
        for pattern in filler_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        budget_patterns = [
            r"(?:不超过|低于|不到|小于|至多|最高)\s*\d+(?:\.\d+)?\s*(?:元|块|rmb)?",
            r"\d+(?:\.\d+)?\s*(?:元|块|rmb)?\s*(?:以下|以内|之内)",
            r"(?:高于|大于|不少于|至少|最低)\s*\d+(?:\.\d+)?\s*(?:元|块|rmb)?",
            r"\d+(?:\.\d+)?\s*(?:元|块|rmb)?\s*(?:以上)",
            r"\d+(?:\.\d+)?\s*(?:元|块|rmb)?\s*(?:到|至|-|~|—)\s*\d+(?:\.\d+)?\s*(?:元|块|rmb)?",
        ]
        for pattern in budget_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r"(?<=\D)的(?=\D|$)", " ", cleaned)
        cleaned = re.sub(r"(?:以内|以下|以上|左右)", " ", cleaned)
        cleaned = re.sub(r"[，。！？、:;,.!?/]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _parse_budget_from_text_v2(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        raw = str(text or "")

        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?\s*(?:到|至|-|~|—)\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?",
            raw,
        )
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            return min(low, high), max(low, high)

        max_match = re.search(
            r"(?:不超过|低于|不到|小于|至多|最高)\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?",
            raw,
        ) or re.search(
            r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?\s*(?:以下|以内|之内)",
            raw,
        )
        if max_match:
            return None, float(max_match.group(1))

        min_match = re.search(
            r"(?:至少|高于|大于|不少于|最低)\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?",
            raw,
        ) or re.search(
            r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?\s*(?:以上)",
            raw,
        )
        if min_match:
            return float(min_match.group(1)), None

        return None, None

    def _parse_budget_from_text_v3(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        raw = str(text or "")

        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?\s*(?:到|至|-|~|—)\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?",
            raw,
        )
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            return min(low, high), max(low, high)

        max_match = re.search(
            r"(?:不超过|低于|不到|小于|至多|最高)\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?",
            raw,
        ) or re.search(
            r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?\s*(?:以下|以内|之内)",
            raw,
        )
        if max_match:
            return None, float(max_match.group(1))

        min_match = re.search(
            r"(?:至少|高于|大于|不少于|最低)\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?",
            raw,
        ) or re.search(
            r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb)?\s*(?:以上)",
            raw,
        )
        if min_match:
            return float(min_match.group(1)), None

        return None, None

    def _parse_budget_from_text(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        raw = str(text or "")

        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:元|块|￥|¥)?\s*(?:-|到|至|~|—)\s*(\d+(?:\.\d+)?)\s*(?:元|块|￥|¥)?",
            raw,
        )
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            return min(low, high), max(low, high)

        max_match = re.search(
            r"(?:不超过|低于|不到|小于)\s*(\d+(?:\.\d+)?)\s*(?:元|块|￥|¥)?",
            raw,
        ) or re.search(
            r"(\d+(?:\.\d+)?)\s*(?:元|块|￥|¥)?\s*(?:以下|以内)",
            raw,
        )
        if max_match:
            return None, float(max_match.group(1))

        min_match = re.search(
            r"(?:至少|高于|大于|不少于|不低于)\s*(\d+(?:\.\d+)?)\s*(?:元|块|￥|¥)?",
            raw,
        ) or re.search(
            r"(\d+(?:\.\d+)?)\s*(?:元|块|￥|¥)?\s*(?:以上)",
            raw,
        )
        if min_match:
            return float(min_match.group(1)), None

        return None, None

    def _matches_budget(
        self,
        price: float,
        budget_min: Optional[float],
        budget_max: Optional[float],
    ) -> bool:
        if budget_min is not None and price < budget_min:
            return False
        if budget_max is not None and price > budget_max:
            return False
        return True

    def _score_product_match(self, product: Product, query: str) -> int:
        if not query:
            return 0

        title = self._normalize_text(product.title)
        description = self._normalize_text(product.description)
        tags = [self._normalize_text(tag) for tag in product.tags]
        full_text = " ".join([title, description, *tags])

        query_text = self._normalize_text(query)
        search_terms = self._build_search_terms(query)
        query_tokens = [t for t in re.split(r"[\s,，/|+_-]+", query_text) if t]

        score = 0
        if query_text and query_text in title:
            score += 100
        elif query_text and query_text in full_text:
            score += 50

        if query_tokens and all(token in full_text for token in query_tokens):
            score += 30

        for term in search_terms:
            if term in title:
                score += 20
            if any(term in tag for tag in tags):
                score += 12
            if term in description:
                score += 6

        return score

    def _rank_products_for_query(self, products: List[Product], query: str) -> List[Product]:
        if not products:
            return []

        scored = []
        for product in products:
            score = self._score_product_match(product, query)
            scored.append((score, product))

        scored.sort(
            key=lambda item: (
                -item[0],
                -item[1].sales,
                item[1].price,
                item[1].product_id,
            )
        )
        return [product for _, product in scored]

    def _scrape_real_data(
        self,
        platform: str,
        query: str,
        max_results: int = None,
        location: str = "",
        sort_order: str = "none",
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        progress_callback=None,
    ) -> List[Product]:
        self.logger.info(f"开始真实爬取 {platform} 平台数据...")

        try:
            requested_limit = max_results or self.max_products_per_platform
            fetch_limit = requested_limit if requested_limit <= 10 else min(requested_limit + 5, requested_limit * 2)
            if platform == "xianyu":
                if XianyuLiveScraper is None:
                    raise RuntimeError("闲鱼实时爬虫不可用，请先安装 playwright 并完成浏览器依赖")

                profile_dir = project_root / "data" / "browser_profiles" / "xianyu"
                with XianyuLiveScraper(
                    profile_dir=profile_dir,
                    headless=self.headless,
                    wait_after_load_ms=self.wait_after_load_ms,
                    logger=self.logger,
                ) as scraper:
                    raw_data = scraper.search(
                        query=query,
                        max_results=fetch_limit,
                        location=location,
                        sort_order=sort_order,
                        price_min=budget_min,
                        price_max=budget_max,
                        progress_callback=self._make_progress_callback(
                            progress_callback,
                            visible_target_count=requested_limit,
                        ),
                    )
                    platform_meta = scraper.stats.to_dict()
                    platform_meta["target_count"] = requested_limit
                    platform_meta = self._normalize_progress_payload(
                        platform_meta,
                        visible_target_count=requested_limit,
                    )
                    self.last_crawl_meta.setdefault("platforms", {})[platform] = platform_meta
                    self.logger.info(
                        f"闲鱼预计总量: {scraper.stats.estimated_total}, 目标: {max_results or self.max_products_per_platform}, 进度: {scraper.stats.progress_text}"
                    )
            else:
                scraper_class = None
                profile_dir = project_root / "data" / "browser_profiles" / platform
                if platform == "taobao":
                    scraper_class = TaobaoLiveScraper
                elif platform == "jd":
                    scraper_class = JDLiveScraper
                elif platform == "pdd":
                    scraper_class = PDDLiveScraper

                if scraper_class is None:
                    raise RuntimeError(f"平台 {platform} 暂未启用真实爬取")
                if scraper_class is TaobaoLiveScraper and TaobaoLiveScraper is None:
                    raise RuntimeError("淘宝实时爬虫不可用，请先安装 playwright 并完成浏览器依赖")
                if scraper_class is JDLiveScraper and JDLiveScraper is None:
                    raise RuntimeError("京东实时爬虫不可用，请先安装 playwright 并完成浏览器依赖")
                if scraper_class is PDDLiveScraper and PDDLiveScraper is None:
                    raise RuntimeError("拼多多实时爬虫不可用，请先安装 playwright 并完成浏览器依赖")

                with scraper_class(
                    profile_dir=profile_dir,
                    headless=self.headless,
                    wait_after_load_ms=self.wait_after_load_ms,
                    logger=self.logger,
                ) as scraper:
                    raw_data = scraper.search(
                        query=query,
                        max_results=fetch_limit,
                        location=location,
                        sort_order=sort_order,
                        price_min=budget_min,
                        price_max=budget_max,
                        progress_callback=self._make_progress_callback(
                            progress_callback,
                            visible_target_count=requested_limit,
                        ),
                    )
                    platform_meta = scraper.stats.to_dict()
                    platform_meta["target_count"] = requested_limit
                    platform_meta = self._normalize_progress_payload(
                        platform_meta,
                        visible_target_count=requested_limit,
                    )
                    self.last_crawl_meta.setdefault("platforms", {})[platform] = platform_meta

            products = []
            for i, item in enumerate(raw_data):
                try:
                    product = self._convert_to_product(item, platform, i)
                    if product:
                        products.append(product)
                except Exception as e:
                    self.logger.error(f"转换商品数据失败: {str(e)}")
                    continue

            self.logger.info(f"成功爬取 {len(products)} 个商品")
            sorted_products = self._sort_products(products, sort_order)
            return sorted_products[:requested_limit]

        except XianyuScrapeBlocked as e:
            self.logger.warning(f"闲鱼被风控或要求登录: {str(e)}")
            raise
        except ImportError as e:
            self.logger.error(f"爬虫模块导入失败: {str(e)}")
            self.logger.info("请确保已安装 selenium: pip install selenium")
            raise
        except Exception as e:
            self.logger.error(f"爬取失败: {str(e)}")
            raise

    def _convert_to_product(self, raw_data: Dict[str, Any], platform: str, index: int) -> Product:
        stable_id = self._build_stable_product_id(raw_data, platform, index)
        seller = Seller(
            name=raw_data.get("seller_name", raw_data.get("shop_name", "未知")),
            rating=4.5,
            reputation_level="普通",
            followers=0,
            response_rate=None,
            ship_speed_score=None,
            service_score=None,
        )

        return Product(
            product_id=stable_id,
            title=raw_data.get("title", ""),
            price=raw_data.get("price", 0.0),
            platform=platform,
            url=raw_data.get("url", ""),
            sales=raw_data.get("sales", 0),
            stock=None,
            seller=seller,
            reviews=[],
            review_count=0,
            positive_rate=0.95,
            images=[raw_data.get("image", "")] if raw_data.get("image") else [],
            description=raw_data.get("description", ""),
            tags=raw_data.get("tags", []),
            crawled_at=datetime.now().isoformat(),
        )

    def _build_stable_product_id(self, raw_data: Dict[str, Any], platform: str, index: int) -> str:
        explicit_id = str(
            raw_data.get("product_id")
            or raw_data.get("item_id")
            or raw_data.get("id")
            or ""
        ).strip()
        if explicit_id:
            return f"{platform}_{explicit_id}"

        url = str(raw_data.get("url") or "").strip()
        parsed = urlparse(url) if url else None
        if parsed:
            query_id = parse_qs(parsed.query).get("id", [""])[0]
            if query_id:
                return f"{platform}_{query_id}"
            tail = parsed.path.rstrip("/").split("/")[-1]
            if tail and tail.isdigit():
                return f"{platform}_{tail}"

        fingerprint = "|".join(
            [
                platform,
                str(raw_data.get("title") or ""),
                str(raw_data.get("price") or ""),
                str(raw_data.get("seller_name") or raw_data.get("shop_name") or ""),
                url,
                str(index),
            ]
        )
        return f"{platform}_{abs(hash(fingerprint))}"

    def _product_location_text(self, item: Dict[str, Any], product: Product) -> str:
        parts = [
            item.get("area", ""),
            item.get("location", ""),
            item.get("address", ""),
            product.title,
            product.description,
        ]
        return " ".join(str(part or "") for part in parts)

    def _sort_products(self, products: List[Product], sort_order: str) -> List[Product]:
        if sort_order == "price_asc":
            return sorted(products, key=lambda p: p.price)
        if sort_order == "price_desc":
            return sorted(products, key=lambda p: p.price, reverse=True)
        return products

    def _log_progress(self, progress: Dict[str, Any]) -> None:
        estimated_total = progress.get("estimated_total", 0)
        crawled_count = progress.get("crawled_count", 0)
        target_count = progress.get("target_count", 0)
        self.logger.info(f"抓取进度: {crawled_count}/{estimated_total or target_count}")

    def _normalize_progress_payload(
        self,
        progress: Dict[str, Any],
        visible_target_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        normalized = dict(progress or {})
        target_count = int(
            visible_target_count
            or normalized.get("target_count")
            or self.max_products_per_platform
            or 0
        )
        crawled_count = min(int(normalized.get("crawled_count", 0) or 0), target_count)
        estimated_total = int(normalized.get("estimated_total", 0) or 0)

        normalized["target_count"] = target_count
        normalized["crawled_count"] = crawled_count
        normalized["underfilled"] = crawled_count < target_count
        normalized["underfilled_by"] = max(0, target_count - crawled_count)
        normalized["progress_text"] = f"{crawled_count}/{estimated_total or target_count}"

        status_message = normalized.get("status_message") or ""
        if status_message:
            status_message = re.sub(r"/\d+\s*个结果", f"/{target_count} 个结果", status_message)
            status_message = re.sub(r"仍缺\s*\d+\s*个", f"仍缺 {normalized['underfilled_by']} 个", status_message)
            normalized["status_message"] = status_message

        return normalized

    def _make_progress_callback(self, external_callback, visible_target_count: Optional[int] = None):
        def callback(progress: Dict[str, Any]) -> None:
            normalized_progress = self._normalize_progress_payload(
                progress,
                visible_target_count=visible_target_count,
            )
            self._log_progress(normalized_progress)
            if external_callback:
                external_callback(normalized_progress)

        return callback

    def save_cache(self, products: List[Product], cache_file: str = None):
        if cache_file is None:
            cache_file = project_root / "data" / "cache" / "products_cache.json"

        cache_data = [p.to_dict() for p in products]
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"缓存已保存到: {cache_file}")


if __name__ == "__main__":
    agent = ScraperAgent()
    products = agent.fetch_products(
        "iPhone 15 Pro",
        platforms=["xianyu", "taobao"],
        location="福建",
        sort_order="price_asc",
    )
    print(f"\n获取到 {len(products)} 个商品")
    for p in products:
        print(f"- [{p.platform}] {p.title}: ¥{p.price}")
    agent.save_cache(products)
