"""Playwright-based live scrapers for Taobao, JD, and PDD."""

import asyncio
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote_plus, urlparse


@dataclass
class MarketplaceScrapeStats:
    """Metadata for a marketplace scrape run."""

    estimated_total: int = 0
    target_count: int = 0
    crawled_count: int = 0
    requested_pages: List[int] = field(default_factory=list)
    blocked_messages: List[str] = field(default_factory=list)
    location: str = ""
    sort_order: str = "none"
    source: str = ""
    underfilled: bool = False
    underfilled_by: int = 0
    status_message: str = ""
    requires_login: bool = False
    risk_detected: bool = False
    final_url: str = ""

    @property
    def progress_text(self) -> str:
        denominator = self.estimated_total or self.target_count or self.crawled_count
        return f"{self.crawled_count}/{max(denominator, 0)}"

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


class _MarketplacePlaywrightBase:
    """Shared Playwright helpers for marketplace scrapers."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        platform: str,
        source: str,
        profile_dir: Optional[Path] = None,
        headless: bool = True,
        timeout_ms: int = 45000,
        wait_after_load_ms: int = 5000,
        logger: Any = None,
    ):
        self.platform = platform
        self.source = source
        self.profile_dir = Path(profile_dir) if profile_dir else None
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.wait_after_load_ms = wait_after_load_ms
        self.logger = logger
        self.stats = MarketplaceScrapeStats(source=source)
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
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("缺少 playwright，请先安装: pip install playwright") from exc

        self.stats = MarketplaceScrapeStats(
            target_count=max(0, int(max_results or 0)),
            location=location or "",
            sort_order=sort_order or "none",
            source=self.source,
        )

        async with async_playwright() as playwright:
            context = await self._open_context(playwright)
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                products = await self._run_search(
                    context=context,
                    page=page,
                    query=query,
                    max_results=max_results,
                    location=location,
                    sort_order=sort_order,
                    price_min=price_min,
                    price_max=price_max,
                    progress_callback=progress_callback,
                )
            finally:
                await self._close_context(context)

        self.stats.crawled_count = len(products)
        self.stats.underfilled = bool(
            self.stats.target_count and len(products) < self.stats.target_count
        )
        self.stats.underfilled_by = max(0, self.stats.target_count - len(products))
        self._emit_progress(progress_callback)
        return products

    async def _run_search(
        self,
        context: Any,
        page: Any,
        query: str,
        max_results: int,
        location: str,
        sort_order: str,
        price_min: Optional[float],
        price_max: Optional[float],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

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
                self._log(
                    "warning",
                    f"{self.platform} 系统 Chrome 启动失败，回退到 Playwright Chromium: {chrome_exc}",
                )
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
                    self._log(
                        "warning",
                        f"{self.platform} 持久化 Profile 不可用，改用 storage_state 会话快照: {profile_exc}",
                    )

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
                self._log(
                    "info",
                    f"{self.platform} 已加载会话快照，复用 {storage_state_path.name}",
                )
            except Exception as exc:
                self._log(
                    "warning",
                    f"{self.platform} 会话快照不可用，改用全新上下文: {exc}",
                )
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
            self._log("warning", f"{self.platform} 保存 storage_state 失败: {exc}")

    async def _patch_context(self, context) -> None:
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            """
        )

    def _emit_progress(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        if callback:
            callback(self.stats.to_dict())

    def _log(self, level: str, message: str) -> None:
        if not self.logger:
            return
        log_method = getattr(self.logger, level, None)
        if callable(log_method):
            log_method(message)

    def _clean_text(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _extract_price(self, raw_price: Any) -> float:
        if isinstance(raw_price, list):
            raw_price = " ".join(str(part) for part in raw_price)
        if isinstance(raw_price, (int, float)):
            return float(raw_price)

        text = self._clean_text(raw_price).replace(",", "")
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
        if not match:
            return 0.0

        price = float(match.group(1))
        if "万" in text:
            price *= 10000
        return price

    def _extract_sales(self, raw_sales: Any) -> int:
        if isinstance(raw_sales, (int, float)):
            return int(raw_sales)

        text = self._clean_text(raw_sales)
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
        if not match:
            return 0

        sales = float(match.group(1))
        if "万" in text:
            sales *= 10000
        elif "千" in text:
            sales *= 1000
        return int(sales)

    def _extract_price_with_scale(self, raw_price: Any, assume_cents: bool = False) -> float:
        if raw_price in (None, "", False):
            return 0.0

        if isinstance(raw_price, (int, float)):
            price = float(raw_price)
            if assume_cents and price > 0:
                return round(price / 100, 2)
            return price

        return self._extract_price(raw_price)

    def _normalize_url(self, raw_url: Any, default_scheme: str = "https") -> str:
        value = self._clean_text(raw_url)
        if not value:
            return ""
        if value.startswith("//"):
            return f"{default_scheme}:{value}"
        if value.startswith("/"):
            return f"{default_scheme}://{self._default_host()}{value}"
        return value

    def _normalize_image(self, raw_url: Any) -> str:
        value = self._clean_text(raw_url)
        if not value:
            return ""
        if value.startswith("//"):
            return "https:" + value
        return value

    def _default_host(self) -> str:
        return ""

    def _sort_products(
        self,
        products: List[Dict[str, Any]],
        sort_order: str,
    ) -> List[Dict[str, Any]]:
        if sort_order == "price_asc":
            return sorted(products, key=lambda item: item.get("price", 0))
        if sort_order == "price_desc":
            return sorted(products, key=lambda item: item.get("price", 0), reverse=True)
        return products

    def _limit_products(
        self,
        products: List[Dict[str, Any]],
        target_count: int,
    ) -> List[Dict[str, Any]]:
        if not target_count or len(products) <= target_count:
            return products
        return products[:target_count]

    def _finalize_products(
        self,
        products: List[Dict[str, Any]],
        target_count: int,
        sort_order: str,
    ) -> List[Dict[str, Any]]:
        ordered = self._sort_products(products, sort_order)
        return self._limit_products(ordered, target_count)

    def _matches_price(
        self,
        product: Dict[str, Any],
        price_min: Optional[float],
        price_max: Optional[float],
    ) -> bool:
        price = float(product.get("price", 0) or 0)
        if price_min is not None and price < price_min:
            return False
        if price_max is not None and price > price_max:
            return False
        return True

    def _append_unique_product(
        self,
        products: List[Dict[str, Any]],
        seen_keys: set,
        product: Optional[Dict[str, Any]],
        price_min: Optional[float],
        price_max: Optional[float],
    ) -> None:
        if not product:
            return
        if not self._matches_price(product, price_min, price_max):
            return

        key = product.get("url") or product.get("product_id") or (
            f"{product.get('title')}|{product.get('price')}|{product.get('seller_name')}"
        )
        if key in seen_keys:
            return

        seen_keys.add(key)
        products.append(product)

    def _append_blocked_message(self, messages: List[str], message: str) -> None:
        cleaned = self._clean_text(message)
        if cleaned and cleaned not in messages:
            messages.append(cleaned)

    def _parse_json_like(self, text: str) -> Optional[Dict[str, Any]]:
        raw = str(text or "").strip()
        if not raw:
            return None

        if raw.startswith("{") and raw.endswith("}"):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None

        match = re.search(r"\((\{[\s\S]*\})\)\s*;?$", raw)
        if not match:
            return None

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def _deep_find_numeric(self, payload: Any, keys: Iterable[str]) -> int:
        wanted = {key.lower() for key in keys}
        values: List[int] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.lower() in wanted:
                        if isinstance(value, str):
                            digits = re.sub(r"[^\d]", "", value)
                            if digits:
                                values.append(int(digits))
                        elif isinstance(value, (int, float)):
                            values.append(int(value))
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        return max(values) if values else 0

    def _extract_generic_dom_cards(
        self,
        raw_cards: List[Dict[str, Any]],
        platform: str,
        price_min: Optional[float],
        price_max: Optional[float],
    ) -> List[Dict[str, Any]]:
        products: List[Dict[str, Any]] = []
        seen = set()
        for raw in raw_cards:
            text = self._clean_text(raw.get("text") or raw.get("title"))
            price = self._extract_price(raw.get("price") or text)
            title = self._clean_text(raw.get("title") or text)
            if not title or price <= 0:
                continue

            product = {
                "title": title[:120],
                "price": price,
                "url": self._normalize_url(raw.get("url")),
                "image": self._normalize_image(raw.get("image")),
                "seller_name": self._clean_text(raw.get("seller_name")) or "未知卖家",
                "sales": self._extract_sales(raw.get("sales") or text),
                "platform": platform,
                "source": f"{platform}_dom",
            }
            self._append_unique_product(products, seen, product, price_min, price_max)

        return products


class TaobaoLiveScraper(_MarketplacePlaywrightBase):
    """Taobao scraper with platform-specific request and state handling."""

    SEARCH_API_MARK = "mtop.relationrecommend.wirelessrecommend.recommend"
    DEFAULT_PAGE_SIZE = 48
    MAX_PAGES = 3

    def __init__(self, **kwargs):
        super().__init__(platform="taobao", source="taobao_search", **kwargs)

    def _default_host(self) -> str:
        return "s.taobao.com"

    async def _run_search(
        self,
        context: Any,
        page: Any,
        query: str,
        max_results: int,
        location: str,
        sort_order: str,
        price_min: Optional[float],
        price_max: Optional[float],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
    ) -> List[Dict[str, Any]]:
        products: List[Dict[str, Any]] = []
        seen = set()
        blocked_messages: List[str] = []
        async def on_response(response):
            url = response.url
            if self.SEARCH_API_MARK not in url:
                return
            try:
                payload = self._parse_json_like(await response.text())
            except Exception:
                payload = None
            if not payload:
                return
            self._extract_taobao_request_hint(url)
            for message in self._extract_taobao_blocked_messages(payload):
                self._append_blocked_message(blocked_messages, message)

            for item in self._iter_taobao_candidates(payload):
                product = self._parse_taobao_candidate(item)
                self._append_unique_product(products, seen, product, price_min, price_max)

        page.on("response", on_response)

        total_pages = min(
            self.MAX_PAGES,
            max(1, math.ceil(max(1, max_results) / self.DEFAULT_PAGE_SIZE)),
        )

        for page_number in range(1, total_pages + 1):
            self.stats.requested_pages.append(page_number)
            await page.goto(
                self._build_search_url(
                    query=query,
                    page_number=page_number,
                    price_min=price_min,
                    price_max=price_max,
                ),
                wait_until="domcontentloaded",
                timeout=self.timeout_ms,
            )
            await page.wait_for_timeout(max(1200, self.wait_after_load_ms))
            self.stats.final_url = page.url

            for frame in page.frames:
                frame_url = self._clean_text(getattr(frame, "url", ""))
                if "login.taobao.com" in frame_url:
                    self.stats.requires_login = True
                    self._append_blocked_message(
                        blocked_messages,
                        "淘宝搜索命中登录校验",
                    )

            dom_products = await self._extract_taobao_dom_products(page, price_min, price_max)
            for product in dom_products:
                self._append_unique_product(products, seen, product, price_min, price_max)

            if len(products) >= max_results:
                break

        if not self.stats.estimated_total:
            self.stats.estimated_total = max(len(products), max_results if products else 0)

        self.stats.blocked_messages = blocked_messages
        self.stats.risk_detected = any("RGV587" in item for item in blocked_messages)
        final_products = self._finalize_products(products, max_results, sort_order)
        self.stats.status_message = self._build_taobao_status(
            actual_count=len(final_products),
            target_count=max_results,
            blocked_messages=blocked_messages,
        )
        self.stats.crawled_count = len(final_products)
        self._emit_progress(progress_callback)
        return final_products

    def _build_search_url(
        self,
        query: str,
        page_number: int,
        price_min: Optional[float],
        price_max: Optional[float],
    ) -> str:
        params = [f"q={quote(query)}"]
        if page_number > 1:
            params.append(f"s={(page_number - 1) * self.DEFAULT_PAGE_SIZE}")
        if price_min is not None:
            params.append(f"start_price={quote(str(price_min))}")
        if price_max is not None:
            params.append(f"end_price={quote(str(price_max))}")
        params.extend(
            [
                "search_type=item",
                "commend=all",
                "sourceId=tb.index",
            ]
        )
        return "https://s.taobao.com/search?" + "&".join(params)

    def _extract_taobao_request_hint(self, url: str) -> None:
        try:
            data_param = parse_qs(urlparse(url).query).get("data", [""])[0]
            payload = json.loads(unquote_plus(data_param))
            params = payload.get("params")
            if isinstance(params, str):
                params = json.loads(params)
            if isinstance(params, dict):
                total = int(params.get("totalResults") or 0)
                if total:
                    self.stats.estimated_total = max(self.stats.estimated_total, total)
        except Exception:
            return

    def _extract_taobao_blocked_messages(self, payload: Dict[str, Any]) -> List[str]:
        ret = payload.get("ret") if isinstance(payload, dict) else None
        if not ret:
            return []
        text = " ".join(str(item) for item in ret)
        risk_words = (
            "RGV587",
            "LOGIN_FAILED",
            "请稍后重试",
            "令牌为空",
            "SESSION失效",
        )
        return [text] if any(word in text for word in risk_words) else []

    def _iter_taobao_candidates(self, payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        stack = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if {"title", "price"}.issubset(current.keys()) or {
                    "item_id",
                    "title",
                }.issubset(current.keys()):
                    yield current
                for value in current.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(current, list):
                stack.extend(item for item in current if isinstance(item, (dict, list)))

    def _parse_taobao_candidate(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        title = self._clean_text(
            item.get("title")
            or item.get("raw_title")
            or item.get("name")
            or item.get("itemTitle")
        )
        price = self._extract_price(
            item.get("price")
            or item.get("priceShow")
            or item.get("view_price")
            or item.get("priceText")
        )
        if not title or price <= 0:
            return None

        item_id = self._clean_text(item.get("item_id") or item.get("nid") or item.get("id"))
        url = self._normalize_url(
            item.get("url")
            or item.get("targetUrl")
            or item.get("item_url")
        )
        if not url and item_id:
            url = f"https://item.taobao.com/item.htm?id={item_id}"

        return {
            "title": title,
            "price": price,
            "url": url,
            "image": self._normalize_image(
                item.get("pic_url")
                or item.get("pic")
                or item.get("image")
            ),
            "seller_name": self._clean_text(
                item.get("nick")
                or item.get("shop_name")
                or item.get("seller_name")
            ) or "未知卖家",
            "sales": self._extract_sales(
                item.get("sales")
                or item.get("dealCnt")
                or item.get("sold")
            ),
            "product_id": item_id,
            "platform": "taobao",
            "source": "taobao_api",
        }

    async def _extract_taobao_dom_products(
        self,
        page: Any,
        price_min: Optional[float],
        price_max: Optional[float],
    ) -> List[Dict[str, Any]]:
        script = """
        () => {
          const cards = [];
          const pushCard = (root) => {
            if (!root) return;
            const text = (root.innerText || root.textContent || '').replace(/\\s+/g, ' ').trim();
            if (!text || !/(¥|￥)\\s*\\d/.test(text)) return;
            const link = root.querySelector('a[href*="item.taobao.com"], a[href*="detail.tmall.com"], a[href^="//"]') || root.querySelector('a[href]');
            const image = root.querySelector('img');
            const titleNode = root.querySelector('[class*="title"], [class*="desc"], img[alt]') || link || root;
            cards.push({
              title: (titleNode.innerText || titleNode.textContent || titleNode.alt || '').replace(/\\s+/g, ' ').trim(),
              text,
              url: link ? (link.href || link.getAttribute('href') || '') : '',
              image: image ? (image.currentSrc || image.src || '') : ''
            });
          };
          const roots = Array.from(document.querySelectorAll('[data-index], [class*="card"], [class*="item"]')).slice(0, 240);
          roots.forEach(pushCard);
          return cards.slice(0, 160);
        }
        """
        products: List[Dict[str, Any]] = []
        seen = set()
        for frame in page.frames:
            frame_url = self._clean_text(getattr(frame, "url", ""))
            if "login.taobao.com" in frame_url:
                continue
            try:
                raw_cards = await frame.evaluate(script)
            except Exception:
                continue
            for product in self._extract_generic_dom_cards(
                raw_cards,
                platform="taobao",
                price_min=price_min,
                price_max=price_max,
            ):
                self._append_unique_product(products, seen, product, price_min, price_max)
        return products

    def _build_taobao_status(
        self,
        actual_count: int,
        target_count: int,
        blocked_messages: List[str],
    ) -> str:
        if actual_count >= target_count > 0:
            return ""
        if self.stats.requires_login and self.stats.risk_detected:
            return "淘宝搜索触发风控并拉起登录校验，当前会话未拿到可用结果"
        if self.stats.requires_login:
            return "淘宝搜索命中登录校验，当前会话未登录，未抓到可用结果"
        if self.stats.risk_detected:
            return "淘宝搜索触发风控（RGV587），当前会话未拿到可用结果"
        if blocked_messages:
            return blocked_messages[0]
        if target_count and actual_count < target_count:
            return f"只抓到 {actual_count}/{target_count} 个淘宝结果，当前会话可见商品不足"
        return ""


class JDLiveScraper(_MarketplacePlaywrightBase):
    """JD scraper with explicit login and risk detection."""

    SEARCH_URL = "https://search.jd.com/Search?keyword={query}&enc=utf-8"

    def __init__(self, **kwargs):
        super().__init__(platform="jd", source="jd_search", **kwargs)

    def _default_host(self) -> str:
        return "search.jd.com"

    async def _run_search(
        self,
        context: Any,
        page: Any,
        query: str,
        max_results: int,
        location: str,
        sort_order: str,
        price_min: Optional[float],
        price_max: Optional[float],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
    ) -> List[Dict[str, Any]]:
        products: List[Dict[str, Any]] = []
        seen = set()
        blocked_messages: List[str] = []
        risk_payload_hint = ""

        async def on_response(response):
            nonlocal risk_payload_hint
            url = response.url
            lower_url = url.lower()
            if "risk_handler" in lower_url:
                self.stats.risk_detected = True
                self._append_blocked_message(blocked_messages, "京东搜索触发验证页")
            if "passport.jd.com" in lower_url:
                self.stats.requires_login = True
            if "api.m.jd.com/api" in lower_url:
                try:
                    payload = await response.json()
                except Exception:
                    payload = None
                if isinstance(payload, dict):
                    raw_data = payload.get("data")
                    if isinstance(raw_data, str):
                        risk_payload_hint = raw_data
                        if "快速验证" in raw_data or "京东验证" in raw_data:
                            self.stats.risk_detected = True
                            self._append_blocked_message(
                                blocked_messages,
                                "京东搜索要求完成快速验证",
                            )
            if "s_new.php" in lower_url:
                try:
                    body = await response.text()
                except Exception:
                    body = ""
                if "errorReason" in body:
                    self.stats.risk_detected = True
                    self._append_blocked_message(blocked_messages, body[:120])

        page.on("response", on_response)
        await page.goto(
            self.SEARCH_URL.format(query=quote(query)),
            wait_until="domcontentloaded",
            timeout=self.timeout_ms,
        )
        await page.wait_for_timeout(max(1200, self.wait_after_load_ms))
        self.stats.final_url = page.url

        if "passport.jd.com" in page.url:
            self.stats.requires_login = True
            self._append_blocked_message(blocked_messages, "京东搜索已跳转登录页")
        if "risk_handler" in page.url:
            self.stats.risk_detected = True

        if not self.stats.requires_login:
            for product in await self._extract_jd_dom_products(page, price_min, price_max):
                self._append_unique_product(products, seen, product, price_min, price_max)

        self.stats.estimated_total = max(len(products), max_results if products else 0)
        if not products and risk_payload_hint:
            self._append_blocked_message(blocked_messages, risk_payload_hint[:120])

        self.stats.blocked_messages = blocked_messages
        final_products = self._finalize_products(products, max_results, sort_order)
        self.stats.status_message = self._build_jd_status(
            actual_count=len(final_products),
            target_count=max_results,
            blocked_messages=blocked_messages,
        )
        self.stats.crawled_count = len(final_products)
        self._emit_progress(progress_callback)
        return final_products

    async def _extract_jd_dom_products(
        self,
        page: Any,
        price_min: Optional[float],
        price_max: Optional[float],
    ) -> List[Dict[str, Any]]:
        script = """
        () => {
          const cards = [];
          const items = Array.from(document.querySelectorAll('li.gl-item, div.gl-i-wrap, [data-sku]')).slice(0, 180);
          for (const item of items) {
            const root = item.closest('li.gl-item') || item;
            const titleNode = root.querySelector('.p-name em, .p-name a, .sku-name');
            const priceNode = root.querySelector('.p-price i, .p-price, [class*="price"]');
            const linkNode = root.querySelector('.p-name a[href], a[href*="//item.jd.com/"]');
            const imageNode = root.querySelector('img[data-lazy-img], img[src]');
            const shopNode = root.querySelector('.curr-shop, .p-shopnum a');
            const salesNode = root.querySelector('[class*="deal"], [class*="comment"]');
            const title = (titleNode?.innerText || titleNode?.textContent || '').replace(/\\s+/g, ' ').trim();
            const price = (priceNode?.innerText || priceNode?.textContent || '').replace(/\\s+/g, ' ').trim();
            if (!title || !price) continue;
            cards.push({
              title,
              price,
              url: linkNode ? (linkNode.href || linkNode.getAttribute('href') || '') : '',
              image: imageNode ? (imageNode.currentSrc || imageNode.src || imageNode.getAttribute('data-lazy-img') || '') : '',
              seller_name: (shopNode?.innerText || shopNode?.textContent || '').replace(/\\s+/g, ' ').trim(),
              sales: (salesNode?.innerText || salesNode?.textContent || '').replace(/\\s+/g, ' ').trim(),
            });
          }
          return cards;
        }
        """
        raw_cards = await page.evaluate(script)
        return self._extract_generic_dom_cards(
            raw_cards,
            platform="jd",
            price_min=price_min,
            price_max=price_max,
        )

    def _build_jd_status(
        self,
        actual_count: int,
        target_count: int,
        blocked_messages: List[str],
    ) -> str:
        if actual_count >= target_count > 0:
            return ""
        if self.stats.requires_login and self.stats.risk_detected:
            return "京东搜索先触发验证，再跳转登录页，当前会话未拿到可用结果"
        if self.stats.requires_login:
            return "京东搜索直接跳转登录页，当前会话未登录"
        if self.stats.risk_detected:
            return "京东搜索触发验证页，当前会话未拿到可用结果"
        if blocked_messages:
            return blocked_messages[0]
        if target_count and actual_count < target_count:
            return f"只抓到 {actual_count}/{target_count} 个京东结果，当前会话可见商品不足"
        return ""


class PDDLiveScraper(_MarketplacePlaywrightBase):
    """Pinduoduo scraper with explicit API status handling."""

    SEARCH_URL = "https://mobile.yangkeduo.com/search_result.html?search_key={query}"
    SEARCH_API_MARK = "/proxy/api/search"

    def __init__(self, **kwargs):
        super().__init__(platform="pdd", source="pdd_search", **kwargs)

    def _default_host(self) -> str:
        return "mobile.yangkeduo.com"

    async def _run_search(
        self,
        context: Any,
        page: Any,
        query: str,
        max_results: int,
        location: str,
        sort_order: str,
        price_min: Optional[float],
        price_max: Optional[float],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
    ) -> List[Dict[str, Any]]:
        products: List[Dict[str, Any]] = []
        seen = set()
        blocked_messages: List[str] = []
        page.set_default_timeout(self.timeout_ms)

        async def on_response(response):
            url = response.url
            lower_url = url.lower()
            if self.SEARCH_API_MARK in lower_url:
                try:
                    payload = await response.json()
                except Exception:
                    payload = None
                if response.status >= 400:
                    self.stats.risk_detected = True
                    error_code = ""
                    if isinstance(payload, dict):
                        error_code = str(payload.get("error_code") or "")
                    if error_code:
                        self._append_blocked_message(
                            blocked_messages,
                            f"拼多多搜索接口返回 {response.status}，error_code={error_code}",
                        )
                    else:
                        self._append_blocked_message(
                            blocked_messages,
                            f"拼多多搜索接口返回 {response.status}",
                        )
                    return

                for item in self._iter_pdd_candidates(payload):
                    product = self._parse_pdd_candidate(item)
                    self._append_unique_product(products, seen, product, price_min, price_max)

        page.on("response", on_response)
        await page.goto(
            self.SEARCH_URL.format(query=quote(query)),
            wait_until="domcontentloaded",
            timeout=self.timeout_ms,
        )
        await page.wait_for_timeout(max(1200, self.wait_after_load_ms))
        self.stats.final_url = page.url

        if "login.html" in page.url:
            self.stats.requires_login = True
            self.stats.risk_detected = True
            self._append_blocked_message(blocked_messages, "拼多多搜索已跳转登录页")
        else:
            try:
                body_text = self._clean_text(await page.locator("body").inner_text(timeout=3000))
            except Exception:
                body_text = ""
            if body_text and "手机登录" in body_text and "验证码" in body_text:
                self.stats.requires_login = True
                self.stats.risk_detected = True
                self._append_blocked_message(blocked_messages, "拼多多搜索命中登录校验")

        # PDD 会在首屏加载后异步触发搜索接口和登录跳转，这里补一段短等待确认最终状态。
        try:
            await page.wait_for_timeout(1500)
        except Exception:
            pass
        self.stats.final_url = page.url
        if "login.html" in page.url:
            self.stats.requires_login = True
            self.stats.risk_detected = True
            self._append_blocked_message(blocked_messages, "拼多多搜索已跳转登录页")

        if not self.stats.requires_login and not products:
            for product in await self._extract_pdd_dom_products(page, price_min, price_max):
                self._append_unique_product(products, seen, product, price_min, price_max)

        self.stats.estimated_total = max(len(products), max_results if products else 0)
        self.stats.blocked_messages = blocked_messages
        final_products = self._finalize_products(products, max_results, sort_order)
        self.stats.status_message = self._build_pdd_status(
            actual_count=len(final_products),
            target_count=max_results,
            blocked_messages=blocked_messages,
        )
        self.stats.crawled_count = len(final_products)
        self._emit_progress(progress_callback)
        return final_products

    def _iter_pdd_candidates(self, payload: Any) -> Iterable[Dict[str, Any]]:
        stack = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if {
                    "goods_id",
                    "goods_name",
                }.issubset(current.keys()) or {
                    "goods_name",
                    "min_group_price",
                }.issubset(current.keys()):
                    yield current
                for value in current.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(current, list):
                stack.extend(item for item in current if isinstance(item, (dict, list)))

    def _parse_pdd_candidate(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        title = self._clean_text(
            item.get("goods_name")
            or item.get("title")
            or item.get("name")
        )
        price = self._extract_price_with_scale(
            item.get("min_group_price")
            or item.get("group_price")
            or item.get("price"),
            assume_cents=True,
        )
        if not title or price <= 0:
            return None

        goods_id = self._clean_text(item.get("goods_id") or item.get("id"))
        url = self._normalize_url(item.get("link_url") or item.get("url"))
        if not url and goods_id:
            url = f"https://mobile.yangkeduo.com/goods.html?goods_id={goods_id}"

        return {
            "title": title,
            "price": price,
            "url": url,
            "image": self._normalize_image(
                item.get("hd_thumb_url")
                or item.get("thumb_url")
                or item.get("image_url")
                or item.get("goods_image_url")
            ),
            "seller_name": self._clean_text(
                item.get("mall_name")
                or item.get("store_name")
                or item.get("seller_name")
            ) or "未知卖家",
            "sales": self._extract_sales(
                item.get("sales_tip")
                or item.get("sales")
                or item.get("sold_quantity")
            ),
            "product_id": goods_id,
            "platform": "pdd",
            "source": "pdd_api",
        }

    async def _extract_pdd_dom_products(
        self,
        page: Any,
        price_min: Optional[float],
        price_max: Optional[float],
    ) -> List[Dict[str, Any]]:
        script = """
        () => {
          const cards = [];
          const items = Array.from(document.querySelectorAll('a[href*="goods"], [data-goods-id], [class*="goods"]')).slice(0, 220);
          for (const item of items) {
            const root = item.closest('[class*="goods"], [class*="card"], li, div') || item;
            const text = (root.innerText || root.textContent || '').replace(/\\s+/g, ' ').trim();
            if (!text || !/(¥|￥|[0-9])/.test(text)) continue;
            const linkNode = root.querySelector('a[href*="goods"]') || item.closest('a[href]');
            const imageNode = root.querySelector('img');
            cards.push({
              title: text,
              text,
              url: linkNode ? (linkNode.href || linkNode.getAttribute('href') || '') : '',
              image: imageNode ? (imageNode.currentSrc || imageNode.src || '') : ''
            });
          }
          return cards;
        }
        """
        raw_cards = await page.evaluate(script)
        return self._extract_generic_dom_cards(
            raw_cards,
            platform="pdd",
            price_min=price_min,
            price_max=price_max,
        )

    def _build_pdd_status(
        self,
        actual_count: int,
        target_count: int,
        blocked_messages: List[str],
    ) -> str:
        if actual_count >= target_count > 0:
            return ""
        if self.stats.requires_login and self.stats.risk_detected:
            return "拼多多搜索接口返回 403，并跳转登录页，当前会话未拿到可用结果"
        if self.stats.requires_login:
            return "拼多多搜索跳转登录页，当前会话未登录"
        if self.stats.risk_detected:
            return "拼多多搜索接口拒绝当前匿名会话，未拿到可用结果"
        if blocked_messages:
            return blocked_messages[0]
        if target_count and actual_count < target_count:
            return f"只抓到 {actual_count}/{target_count} 个拼多多结果，当前会话可见商品不足"
        return ""
