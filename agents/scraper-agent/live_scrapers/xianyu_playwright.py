"""Playwright-based live scraper for Xianyu/Goofish search results."""

import asyncio
import hashlib
import json
import math
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, quote, unquote_plus, urlparse

import requests


class XianyuScrapeBlocked(RuntimeError):
    """Raised when Goofish returns a risk-control or anti-bot response."""


@dataclass
class XianyuScrapeStats:
    """Metadata for a scrape run."""

    estimated_total: int = 0
    target_count: int = 0
    crawled_count: int = 0
    requested_pages: List[int] = field(default_factory=list)
    blocked_messages: List[str] = field(default_factory=list)
    location: str = ""
    sort_order: str = "none"
    source: str = "goofish"
    underfilled: bool = False
    underfilled_by: int = 0
    status_message: str = ""
    requires_login: bool = False
    risk_detected: bool = False
    final_url: str = ""

    @property
    def progress_text(self) -> str:
        denominator = self.estimated_total or self.target_count
        if denominator <= 0:
            return f"{self.crawled_count}/0"
        return f"{self.crawled_count}/{denominator}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimated_total": self.estimated_total,
            "target_count": self.target_count,
            "crawled_count": self.crawled_count,
            "progress_text": self.progress_text,
            "requested_pages": self.requested_pages,
            "blocked_messages": self.blocked_messages,
            "location": self.location,
            "sort_order": self.sort_order,
            "source": self.source,
            "underfilled": self.underfilled,
            "underfilled_by": self.underfilled_by,
            "status_message": self.status_message,
            "requires_login": self.requires_login,
            "risk_detected": self.risk_detected,
            "final_url": self.final_url,
        }


class XianyuLiveScraper:
    """Scrape Xianyu by observing Goofish API traffic."""

    SEARCH_URL = "https://www.goofish.com/search?q={query}{extra}"
    SEARCH_API_MARK = "h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search"
    SEARCH_API_URL = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/"
    SEARCH_API_NAME = "mtop.taobao.idlemtopsearch.pc.search"
    APP_KEY = "34839810"
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
    DEFAULT_PAGE_SIZE = 30
    MAX_EFFECTIVE_PAGES = 50
    MAX_EMPTY_API_PAGES = 2
    MAX_NO_MATCH_PAGES = 4
    MAX_FILTERED_NO_MATCH_PAGES = 10
    PAGE_REQUEST_DELAY_RANGE = (0.35, 0.85)
    LOCATION_MATCH_RATE = 0.05

    def __init__(
        self,
        profile_dir: Optional[Path] = None,
        headless: bool = False,
        timeout_ms: int = 45000,
        wait_after_load_ms: int = 5000,
        logger: Any = None,
    ):
        self.profile_dir = Path(profile_dir) if profile_dir else None
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.wait_after_load_ms = wait_after_load_ms
        self.logger = logger
        self.stats = XianyuScrapeStats()
        self._browser = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def search(
        self,
        query: str,
        max_results: int = 50,
        location: str = "",
        sort_order: str = "none",
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        return asyncio.run(
            self.search_async(
                query=query,
                max_results=max_results,
                location=location,
                sort_order=sort_order,
                price_min=price_min,
                price_max=price_max,
                progress_callback=progress_callback,
            )
        )

    async def search_async(
        self,
        query: str,
        max_results: int = 50,
        location: str = "",
        sort_order: str = "none",
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        return await self._run(
            query=query,
            target_count=max_results,
            location=location,
            sort_order=sort_order,
            price_min=price_min,
            price_max=price_max,
            probe_only=False,
            progress_callback=progress_callback,
        )

    async def _run(
        self,
        query: str,
        target_count: int,
        location: str,
        sort_order: str,
        price_min: Optional[float],
        price_max: Optional[float],
        probe_only: bool,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("缺少 playwright，请先安装: pip install playwright") from exc

        products: List[Dict[str, Any]] = []
        seen_keys = set()
        api_page_counts: List[int] = []
        blocked_messages: List[str] = []
        request_context: Dict[str, Any] = {}

        self.stats = XianyuScrapeStats(
            target_count=max(0, int(target_count or 0)),
            location=location or "",
            sort_order=sort_order or "none",
        )

        def collect_product(product: Dict[str, Any]) -> None:
            if not product:
                return
            if not self._matches_price(product, price_min, price_max):
                return
            if not self._matches_location(product, location):
                return

            key = product.get("url") or f"{product.get('title')}|{product.get('price')}"
            if key in seen_keys:
                return

            seen_keys.add(key)
            products.append(product)
            capped_count = min(len(products), self.stats.target_count or len(products))
            if capped_count != self.stats.crawled_count:
                self.stats.crawled_count = capped_count
                self._emit_progress(progress_callback)

        def process_payload(payload: Dict[str, Any], collect_items: bool) -> int:
            for message in self._extract_blocked_messages(payload):
                if message not in blocked_messages:
                    blocked_messages.append(message)

            items = list(self._iter_api_items(payload))
            if not items:
                return 0

            api_page_counts.append(len(items))
            inferred_total = self._extract_total(payload, items)
            if inferred_total:
                self.stats.estimated_total = max(self.stats.estimated_total, inferred_total)

            if not collect_items:
                return len(items)

            for item in items:
                collect_product(self._parse_api_item(item))
            return len(items)

        async with async_playwright() as playwright:
            context = await self._open_context(playwright)
            page = context.pages[0] if context.pages else await context.new_page()

            async def on_request(request):
                if self.SEARCH_API_MARK not in request.url or "shade" in request.url:
                    return
                try:
                    request_context["headers"] = await request.all_headers()
                except Exception:
                    request_context["headers"] = {}
                request_context["url"] = request.url
                request_context["post_data"] = request.post_data or ""

            async def on_response(response):
                if self.SEARCH_API_MARK not in response.url or "shade" in response.url:
                    return
                try:
                    payload = await response.json()
                except Exception:
                    return
                process_payload(payload, collect_items=not probe_only)

            page.on("request", on_request)
            page.on("response", on_response)

            try:
                await self._goto_search(page, query, location, page_number=1)
                self.stats.final_url = page.url
                await self._wait_for_initial_capture(request_context, api_page_counts)
                self.stats.final_url = page.url

                block_message = await self._detect_page_blocked(page)
                if block_message and block_message not in blocked_messages:
                    blocked_messages.append(block_message)

                self._apply_block_flags(blocked_messages)

                if not probe_only and not api_page_counts:
                    dom_products = await self._extract_visible_cards(page)
                    for product in dom_products:
                        collect_product(product)

                if not self.stats.estimated_total:
                    self.stats.estimated_total = self._fallback_total_estimate(len(products), api_page_counts)

                self._emit_progress(progress_callback)

                if (
                    not probe_only
                    and len(products) < max(1, int(target_count or 1))
                    and request_context.get("post_data")
                    and request_context.get("url")
                ):
                    await self._collect_remaining_pages(
                        query=query,
                        target_count=max(1, int(target_count or 1)),
                        location=location,
                        price_min=price_min,
                        price_max=price_max,
                        request_context=request_context,
                        context=context,
                        api_page_counts=api_page_counts,
                        blocked_messages=blocked_messages,
                        products=products,
                        process_payload=process_payload,
                    )
            finally:
                await self._close_context(context)

        self.stats.blocked_messages = blocked_messages
        self._apply_block_flags(blocked_messages)
        self.stats.crawled_count = min(len(products), max(0, target_count or len(products)))

        if probe_only:
            return []

        if not products and blocked_messages:
            if api_page_counts or self.stats.estimated_total:
                self.stats.underfilled = bool(target_count)
                self.stats.underfilled_by = max(0, int(target_count or 0))
                self.stats.status_message = self._build_status_message(
                    actual_count=0,
                    target_count=int(target_count or 0),
                    blocked_messages=blocked_messages,
                    location=location,
                )
                self._emit_progress(progress_callback)
                return []
            raise XianyuScrapeBlocked("; ".join(blocked_messages[:3]))

        if not products:
            if location and api_page_counts:
                scanned_count = sum(api_page_counts)
                scanned_pages = len(api_page_counts)
                self.stats.underfilled = bool(target_count)
                self.stats.underfilled_by = max(0, int(target_count or 0))
                self.stats.status_message = (
                    f"\u5df2\u626b\u63cf\u7ea6 {scanned_count} \u6761\u5019\u9009\u7ed3\u679c"
                    f"\uff08\u7ea6 {scanned_pages} \u9875\uff09\uff0c"
                    f"\u4f46\u672a\u627e\u5230\u5339\u914d\u5730\u533a\u201c{location}\u201d\u7684\u5546\u54c1"
                )
                self._emit_progress(progress_callback)
                return []
                raise RuntimeError(
                    f"闲鱼已扫描约 {scanned_count} 条候选结果（约 {scanned_pages} 页），"
                    f"但没有匹配地区“{location}”的商品。"
                )
            raise RuntimeError("闲鱼页面返回成功，但没有解析到有效商品，可能是页面结构变更或请求被限制。")

        sampled = self._random_sample(products, target_count)
        sorted_products = self._sort_products(sampled, sort_order)
        self.stats.crawled_count = len(sorted_products)
        self.stats.underfilled = bool(target_count and len(sorted_products) < target_count)
        self.stats.underfilled_by = max(0, int(target_count or 0) - len(sorted_products))
        self.stats.status_message = self._build_status_message(
            actual_count=len(sorted_products),
            target_count=int(target_count or 0),
            blocked_messages=blocked_messages,
            location=location,
        )
        self._emit_progress(progress_callback)
        return sorted_products

    async def _collect_remaining_pages(
        self,
        query: str,
        target_count: int,
        location: str,
        price_min: Optional[float],
        price_max: Optional[float],
        request_context: Dict[str, Any],
        context: Any,
        api_page_counts: List[int],
        blocked_messages: List[str],
        products: List[Dict[str, Any]],
        process_payload: Callable[[Dict[str, Any], bool], int],
    ) -> None:
        page_size = max(api_page_counts + [self.DEFAULT_PAGE_SIZE])
        next_page = 2
        empty_api_streak = 0
        no_match_streak = 0
        filtered_mode = bool(location or price_min is not None or price_max is not None)

        while len(products) < target_count:
            total_pages = self._estimate_total_pages(
                page_size=page_size,
                target_count=target_count,
                location=location,
                price_filtered=filtered_mode,
            )
            if next_page > total_pages:
                break

            page_number = next_page
            next_page += 1
            before_count = len(products)
            self.stats.requested_pages.append(page_number)

            await asyncio.sleep(self._next_request_delay())
            payload = await self._fetch_api_page_payload(
                page_number=page_number,
                query=query,
                request_context=request_context,
                cookies=await context.cookies(),
            )

            if payload:
                page_items = process_payload(payload, collect_items=True)
                page_size = max(api_page_counts + [page_size, self.DEFAULT_PAGE_SIZE])
            else:
                page_items = 0

            new_count = len(products) - before_count
            empty_api_streak = empty_api_streak + 1 if page_items <= 0 else 0
            no_match_streak = no_match_streak + 1 if new_count <= 0 else 0

            if blocked_messages and new_count <= 0:
                self._log("warning", "闲鱼后续分页触发风控，返回当前已抓到的部分结果")
                break
            if empty_api_streak >= self.MAX_EMPTY_API_PAGES:
                break

            no_match_limit = self.MAX_FILTERED_NO_MATCH_PAGES if filtered_mode else self.MAX_NO_MATCH_PAGES
            if no_match_streak >= no_match_limit:
                break

    async def _wait_for_initial_capture(
        self,
        request_context: Dict[str, Any],
        api_page_counts: List[int],
        timeout_ms: int = 2500,
    ) -> None:
        deadline = time.monotonic() + (timeout_ms / 1000)
        while time.monotonic() < deadline:
            if api_page_counts or request_context.get("post_data"):
                return
            await asyncio.sleep(0.1)

    async def _open_context(self, playwright):
        self._browser = None
        context_options = {
            "locale": "zh-CN",
            "viewport": {"width": 1366, "height": 900},
            "user_agent": self.DEFAULT_USER_AGENT,
            "timezone_id": "Asia/Shanghai",
        }
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]

        if self.profile_dir and not self.headless:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            try:
                context = await playwright.chromium.launch_persistent_context(
                    str(self.profile_dir),
                    headless=self.headless,
                    channel="chrome",
                    args=launch_args,
                    ignore_default_args=["--enable-automation"],
                    **context_options,
                )
                await self._patch_context(context)
                return context
            except Exception as chrome_exc:
                self._log("warning", f"系统 Chrome 启动失败，回退到 Playwright Chromium: {chrome_exc}")
                try:
                    context = await playwright.chromium.launch_persistent_context(
                        str(self.profile_dir),
                        headless=self.headless,
                        args=launch_args,
                        ignore_default_args=["--enable-automation"],
                        **context_options,
                    )
                    await self._patch_context(context)
                    return context
                except Exception as profile_exc:
                    self._log("warning", f"闲鱼持久化 Profile 不可用，改用 storage_state 会话快照: {profile_exc}")

        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
            ignore_default_args=["--enable-automation"],
        )
        storage_state_path = self._storage_state_path()
        if storage_state_path:
            try:
                context = await browser.new_context(
                    **{
                        **context_options,
                        "storage_state": str(storage_state_path),
                    }
                )
                self._log("info", f"闲鱼已加载会话快照，复用 {storage_state_path.name}")
            except Exception as exc:
                self._log("warning", f"闲鱼会话快照不可用，改用全新上下文: {exc}")
                context = await browser.new_context(**context_options)
        else:
            context = await browser.new_context(**context_options)
        self._browser = browser
        await self._patch_context(context)
        return context

    async def _close_context(self, context) -> None:
        try:
            await self._persist_storage_state(context)
            await context.close()
        finally:
            if self._browser:
                await self._browser.close()
                self._browser = None

    def _storage_state_path(self) -> Optional[Path]:
        if not self.profile_dir:
            return None
        path = self.profile_dir / "storage_state.json"
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            return path
        return None

    async def _persist_storage_state(self, context) -> None:
        if not self.profile_dir:
            return
        try:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(self.profile_dir / "storage_state.json"))
        except Exception as exc:
            self._log("warning", f"闲鱼保存 storage_state 失败: {exc}")

    async def _patch_context(self, context) -> None:
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            """
        )

    async def _goto_search(self, page, query: str, location: str, page_number: int) -> None:
        extra = self._build_query_extra(location=location, page_number=page_number)
        await page.goto(
            self.SEARCH_URL.format(query=quote(query), extra=extra),
            wait_until="domcontentloaded",
            timeout=self.timeout_ms,
        )
        await self._wait_after_search(page)

    async def _wait_after_search(self, page) -> None:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(max(800, self.wait_after_load_ms))

    def _build_query_extra(self, location: str, page_number: int) -> str:
        params = []
        if page_number > 1:
            params.append(f"page={page_number}")
        return ("&" + "&".join(params)) if params else ""

    def _estimate_total_pages(
        self,
        page_size: int,
        target_count: int,
        location: str = "",
        price_filtered: bool = False,
    ) -> int:
        safe_page_size = max(1, int(page_size or self.DEFAULT_PAGE_SIZE))
        estimated_items = max(int(self.stats.estimated_total or 0), int(target_count or 0))
        total_pages = max(1, math.ceil(max(estimated_items, safe_page_size) / safe_page_size))

        if location:
            expected_location_pages = math.ceil(
                max(1, target_count) / max(1, safe_page_size * self.LOCATION_MATCH_RATE)
            )
            total_pages = max(total_pages, expected_location_pages)
        elif price_filtered:
            total_pages = max(total_pages, math.ceil(max(1, target_count * 2) / safe_page_size))

        if not self.stats.estimated_total:
            buffer_pages = 4 if location or price_filtered else 2
            total_pages = max(
                total_pages,
                math.ceil(max(1, target_count) / safe_page_size) + buffer_pages,
            )

        return min(total_pages, self.MAX_EFFECTIVE_PAGES)

    def _next_request_delay(self) -> float:
        low, high = self.PAGE_REQUEST_DELAY_RANGE
        return random.uniform(low, high)

    def _iter_api_items(self, payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        result_list = data.get("resultList", []) if isinstance(data, dict) else []
        return result_list if isinstance(result_list, list) else []

    def _extract_total(self, payload: Dict[str, Any], items: List[Dict[str, Any]]) -> int:
        candidates: List[int] = []
        for key in (
            "total",
            "totalCount",
            "count",
            "totalResults",
            "resultCount",
            "numFound",
            "sellingOrder",
        ):
            value = self._deep_find(payload, key)
            if isinstance(value, str):
                digits = re.sub(r"[^\d]", "", value)
                if digits:
                    candidates.append(int(digits))
            elif isinstance(value, (int, float)):
                candidates.append(int(value))

        if candidates:
            return min(max(candidates), self.MAX_EFFECTIVE_PAGES * self.DEFAULT_PAGE_SIZE)
        return 0

    def _fallback_total_estimate(self, product_count: int, api_page_counts: List[int]) -> int:
        page_count = max(api_page_counts + [0])
        if product_count <= 0 and page_count <= 0:
            return 0
        if page_count > 0:
            return min(max(page_count, self.DEFAULT_PAGE_SIZE), self.MAX_EFFECTIVE_PAGES * self.DEFAULT_PAGE_SIZE)
        return min(product_count, self.MAX_EFFECTIVE_PAGES * self.DEFAULT_PAGE_SIZE)

    def _parse_api_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        main = self._safe_get(item, "data", "item", "main", default={})
        if not isinstance(main, dict):
            return None

        ex_content = main.get("exContent", {})
        if not isinstance(ex_content, dict):
            ex_content = {}
        click_args = self._safe_get(main, "clickParam", "args", default={})
        if not isinstance(click_args, dict):
            click_args = {}

        title = self._clean_text(
            ex_content.get("title")
            or self._rich_text_to_string(ex_content.get("richTitle"))
            or main.get("title")
        )
        price = self._extract_price(
            ex_content.get("price")
            or click_args.get("displayPrice")
            or click_args.get("price")
            or main.get("price")
        )
        url = self._normalize_url(
            main.get("targetUrl")
            or ex_content.get("targetUrl")
            or click_args.get("targetUrl")
            or click_args.get("item_id")
            or click_args.get("id")
        )
        image = self._normalize_image(ex_content.get("picUrl") or main.get("picUrl"))
        seller_name = self._clean_text(
            ex_content.get("userNickName")
            or ex_content.get("nick")
            or click_args.get("sellerNick")
        )
        area = self._clean_text(ex_content.get("area") or ex_content.get("district") or click_args.get("area"))
        publish_time = click_args.get("publishTime")

        if not title or price <= 0:
            return None

        return {
            "title": title,
            "price": price,
            "url": url,
            "image": image,
            "seller_name": seller_name or "未知卖家",
            "area": area,
            "location": area,
            "publish_time": publish_time,
            "platform": "xianyu",
            "source": "goofish_api",
        }

    async def _extract_visible_cards(self, page) -> List[Dict[str, Any]]:
        script = """
        () => {
          const cards = [];
          const anchors = Array.from(document.querySelectorAll('a[href]')).slice(0, 600);
          for (const anchor of anchors) {
            const href = anchor.href || '';
            const text = (anchor.innerText || anchor.textContent || '').replace(/\\s+/g, ' ').trim();
            const card = anchor.closest('[class*="card"], [class*="item"], [class*="feeds"], div') || anchor;
            const cardText = (card.innerText || card.textContent || text || '').replace(/\\s+/g, ' ').trim();
            const priceMatch = cardText.match(/(?:¥|￥)\\s*([0-9]+(?:\\.[0-9]+)?(?:万)?)/);
            if (!priceMatch || cardText.length < 4) continue;
            const img = card.querySelector('img');
            cards.push({
              title: text || cardText,
              text: cardText,
              url: href,
              image: img ? (img.currentSrc || img.src || '') : ''
            });
          }
          return cards.slice(0, 120);
        }
        """
        raw_cards = await page.evaluate(script)
        products: List[Dict[str, Any]] = []

        for raw in raw_cards:
            text = raw.get("text") or raw.get("title") or ""
            title = self._derive_title_from_dom(text)
            price = self._extract_price(text)
            location = self._extract_location_from_text(text)
            # 尝试从文本中提取卖家昵称
            seller_name = self._extract_seller_from_text(text)
            if not title or price <= 0:
                continue
            products.append(
                {
                    "title": title,
                    "price": price,
                    "url": self._normalize_url(raw.get("url")),
                    "image": self._normalize_image(raw.get("image")),
                    "seller_name": seller_name or "未知卖家",
                    "area": location,
                    "location": location,
                    "platform": "xianyu",
                    "source": "goofish_dom",
                }
            )

        return products

    def _random_sample(self, products: List[Dict[str, Any]], target_count: int) -> List[Dict[str, Any]]:
        if not target_count or len(products) <= target_count:
            return products
        return random.sample(products, target_count)

    def _sort_products(self, products: List[Dict[str, Any]], sort_order: str) -> List[Dict[str, Any]]:
        if sort_order == "price_asc":
            return sorted(products, key=lambda item: item.get("price", 0))
        if sort_order == "price_desc":
            return sorted(products, key=lambda item: item.get("price", 0), reverse=True)
        return products

    def _matches_price(
        self,
        product: Dict[str, Any],
        price_min: Optional[float],
        price_max: Optional[float],
    ) -> bool:
        try:
            price = float(product.get("price", 0) or 0)
        except (TypeError, ValueError):
            return False

        if price_min is not None and price < price_min:
            return False
        if price_max is not None and price > price_max:
            return False
        return True

    def _emit_progress(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        if callback:
            callback(self.stats.to_dict())

    def _matches_location(self, product: Dict[str, Any], location: str) -> bool:
        if not location:
            return True

        text = self._location_text(product)
        if location == "福建":
            return any(city in text for city in self._fujian_locations())
        if location in text:
            return True
        if location in self._fujian_locations():
            return "福建" in text
        return False

    def _location_text(self, product: Dict[str, Any]) -> str:
        return " ".join(str(product.get(key) or "") for key in ("area", "location", "title", "description"))

    def _extract_blocked_messages(self, payload: Dict[str, Any]) -> List[str]:
        ret = payload.get("ret") if isinstance(payload, dict) else None
        if not ret:
            return []

        text = " ".join(str(item) for item in ret)
        risk_words = (
            "RGV587",
            "FAIL_SYS_USER_VALIDATE",
            "验证码",
            "被挤爆",
            "风控",
            "非法访问",
            "正常浏览器访问",
        )
        return [text] if any(word in text for word in risk_words) else []

    def _apply_block_flags(self, blocked_messages: List[str]) -> None:
        text = " ".join(blocked_messages or [])
        if not text:
            return
        if any(token in text for token in ("登录", "login", "验证码", "验证")):
            self.stats.requires_login = True
        if any(token in text for token in ("RGV587", "风控", "非法访问", "被挤爆", "正常浏览器访问")):
            self.stats.risk_detected = True

    async def _fetch_api_page_payload(
        self,
        page_number: int,
        query: str,
        request_context: Dict[str, Any],
        cookies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not request_context.get("post_data") or not request_context.get("url"):
            return None

        try:
            body = {key: values[0] for key, values in parse_qs(request_context["post_data"]).items()}
            data_obj = json.loads(unquote_plus(body["data"]))
        except Exception as exc:
            self._log("warning", f"闲鱼后续分页请求体解析失败: {exc}")
            return None

        data_obj["pageNumber"] = page_number
        data_obj["keyword"] = query
        data_str = json.dumps(data_obj, ensure_ascii=False, separators=(",", ":"))

        cookie_map = {item["name"]: item["value"] for item in cookies if "name" in item and "value" in item}
        token_bundle = cookie_map.get("_m_h5_tk", "")
        if "_" not in token_bundle:
            self._log("warning", "闲鱼 Cookie 中缺少 _m_h5_tk，无法请求后续页")
            return None

        token = token_bundle.split("_", 1)[0]
        timestamp = str(int(time.time() * 1000))
        sign = hashlib.md5(f"{token}&{timestamp}&{self.APP_KEY}&{data_str}".encode("utf-8")).hexdigest()

        request_headers = request_context.get("headers", {})
        headers = {
            "accept": request_headers.get("accept", "application/json, text/plain, */*"),
            "accept-language": request_headers.get("accept-language", "zh-CN,zh;q=0.9"),
            "content-type": request_headers.get("content-type", "application/x-www-form-urlencoded"),
            "origin": "https://www.goofish.com",
            "referer": f"https://www.goofish.com/search?q={quote(query)}&spm=a21ybx.home.searchInput.0",
            "user-agent": request_headers.get("user-agent", self.DEFAULT_USER_AGENT),
        }
        for key in (
            "bx-ua",
            "bx-umidtoken",
            "bx_et",
            "sec-ch-ua",
            "sec-ch-ua-mobile",
            "sec-ch-ua-platform",
        ):
            value = request_headers.get(key)
            if value:
                headers[key] = value

        body["data"] = data_str
        params = {
            "jsv": "2.7.2",
            "appKey": self.APP_KEY,
            "t": timestamp,
            "sign": sign,
            "v": "1.0",
            "type": "originaljson",
            "accountSite": "xianyu",
            "dataType": "json",
            "timeout": "20000",
            "api": self.SEARCH_API_NAME,
            "sessionOption": "AutoLoginOnly",
            "spm_cnt": "a21ybx.search.0.0",
            "spm_pre": "a21ybx.home.searchInput.0",
        }

        try:
            response = requests.post(
                self.SEARCH_API_URL,
                params=params,
                data=body,
                headers=headers,
                cookies=cookie_map,
                timeout=max(15, self.timeout_ms / 1000),
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            self._log("warning", f"闲鱼接口续抓第 {page_number} 页失败: {exc}")
            return None
        except ValueError as exc:
            self._log("warning", f"闲鱼接口续抓第 {page_number} 页返回了非法 JSON: {exc}")
            return None

        self._log("info", f"闲鱼接口续抓第 {page_number} 页成功")
        return payload

    async def _detect_page_blocked(self, page) -> str:
        try:
            body_text = await page.locator("body").inner_text(timeout=3000)
        except Exception:
            return ""

        for phrase in ("非法访问", "正常浏览器访问", "验证码", "被挤爆"):
            if phrase in body_text:
                return f"页面提示: {phrase}"
        return ""

    def _build_status_message(
        self,
        actual_count: int,
        target_count: int,
        blocked_messages: List[str],
        location: str,
    ) -> str:
        if target_count and actual_count < target_count:
            shortage = target_count - actual_count
            if blocked_messages:
                return f"只抓到 {actual_count}/{target_count} 个结果，后续分页触发风控，仍缺 {shortage} 个"
            if location:
                return f"只抓到 {actual_count}/{target_count} 个结果，当前地区筛选较严，仍缺 {shortage} 个"
            return f"只抓到 {actual_count}/{target_count} 个结果，已用尽可用分页或有效候选不足"
        if blocked_messages:
            return "抓取完成，但过程中出现过风控提示"
        return ""

    def _extract_price(self, raw_price: Any) -> float:
        if isinstance(raw_price, list):
            raw_price = "".join(str(part.get("text", "")) for part in raw_price if isinstance(part, dict))

        price_text = str(raw_price or "").replace("当前价", "").replace(",", "").strip()
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", price_text)
        if not match:
            return 0.0

        price = float(match.group(1))
        if "万" in price_text:
            price *= 10000
        return price

    def _rich_text_to_string(self, raw_text: Any) -> str:
        if isinstance(raw_text, list):
            return "".join(
                str(part.get("text") or part.get("content") or "")
                for part in raw_text
                if isinstance(part, dict)
            )
        return self._clean_text(raw_text)

    def _derive_title_from_dom(self, text: str) -> str:
        text = self._clean_text(text)
        text = re.sub(r"(?:¥|￥)\s*\d+(?:\.\d+)?(?:万)?", " ", text)
        text = re.sub(r"\b\d+人想要\b|\b\d+浏览\b", " ", text)
        return self._clean_text(text)[:120]

    def _extract_location_from_text(self, text: str) -> str:
        for city in self._fujian_locations():
            if city in text:
                return city
        return ""

    def _extract_seller_from_text(self, text: str) -> str:
        """从闲鱼卡片文本中提取卖家昵称"""
        import re
        # 闲鱼卡片格式通常是: ... 地区 昵称 想要数
        # 尝试匹配地区后面的昵称
        for city in self._fujian_locations():
            if city in text:
                after_city = text.split(city, 1)[1].strip()
                # 提取城市后面的第一段纯中文/字母/数字组成的昵称
                match = re.match(r'([一-龥a-zA-Z0-9_]{2,16})', after_city)
                if match:
                    return match.group(1)
                break
        # 备用: 尝试从"想要"前面提取
        want_match = re.search(r'([一-龥a-zA-Z0-9_]{2,16})\s*\d+\s*想要', text)
        if want_match:
            return want_match.group(1)
        # 最后尝试从文本末尾提取可能的昵称
        parts = text.split()
        for part in reversed(parts):
            part = part.strip()
            if re.match(r'^[一-龥a-zA-Z0-9_]{2,12}$', part) and '¥' not in part:
                return part
        return ""

    def _normalize_url(self, url: Any) -> str:
        value = str(url or "").strip()
        if not value:
            return ""
        if value.startswith("fleamarket://"):
            parsed = urlparse(value)
            query = parse_qs(parsed.query)
            item_id = query.get("id", [""])[0] or query.get("itemId", [""])[0]
            if item_id:
                return f"https://www.goofish.com/item?id={item_id}"
            return value.replace("fleamarket://", "https://www.goofish.com/")
        if value.startswith("//"):
            return "https:" + value
        if value.isdigit():
            return f"https://www.goofish.com/item?id={value}"
        return value

    def _normalize_image(self, url: Any) -> str:
        value = str(url or "").strip()
        if not value:
            return ""
        if value.startswith("//"):
            return "https:" + value
        return value

    def _clean_text(self, text: Any) -> str:
        if isinstance(text, (dict, list)):
            text = json.dumps(text, ensure_ascii=False)
        return re.sub(r"\s+", " ", str(text or "")).strip()

    def _safe_get(self, data: Any, *keys: str, default: Any = "") -> Any:
        current = data
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def _deep_find(self, data: Any, key_name: str) -> Any:
        if isinstance(data, dict):
            if key_name in data:
                return data[key_name]
            for value in data.values():
                found = self._deep_find(value, key_name)
                if found is not None:
                    return found
        elif isinstance(data, list):
            for value in data:
                found = self._deep_find(value, key_name)
                if found is not None:
                    return found
        return None

    def _fujian_locations(self) -> List[str]:
        return [
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

    def _log(self, level: str, message: str) -> None:
        if not self.logger:
            return
        log_func = getattr(self.logger, level, None) or getattr(self.logger, "info", None)
        if log_func:
            log_func(message)
