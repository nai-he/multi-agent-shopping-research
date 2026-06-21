"""Smoke checks for the real scraper workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "agents" / "scraper-agent"))

from agent import ScraperAgent  # noqa: E402


def _safe_print(message: str = "") -> None:
    text = str(message)
    try:
        print(text)
    except UnicodeEncodeError:
        encoded = text.encode(sys.stdout.encoding or "utf-8", errors="replace")
        print(encoded.decode(sys.stdout.encoding or "utf-8", errors="replace"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行真实爬虫冒烟诊断")
    parser.add_argument(
        "--query",
        default="iPhone 15",
        help="要搜索的关键词，默认 iPhone 15",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=["xianyu"],
        help="要测试的平台列表，默认 xianyu",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="每个平台最多抓取多少条结果，默认 5",
    )
    return parser


def run_smoke_check(query: str, platforms: list[str], limit: int) -> int:
    agent = ScraperAgent()
    products = agent.fetch_products(
        query=query,
        platforms=platforms,
        max_results_per_platform=max(1, limit),
    )

    payload = {
        "query": query,
        "platforms": platforms,
        "products_count": len(products),
        "crawl_meta": agent.last_crawl_meta,
        "sample_products": [
            {
                "title": product.title,
                "price": product.price,
                "platform": product.platform,
                "url": product.url,
            }
            for product in products[: min(5, len(products))]
        ],
    }
    _safe_print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def test_real_scraper_smoke() -> None:
    exit_code = run_smoke_check(query="iPhone 15", platforms=["xianyu"], limit=1)
    assert exit_code == 0


def main() -> int:
    args = build_parser().parse_args()
    return run_smoke_check(
        query=args.query,
        platforms=list(args.platforms),
        limit=args.limit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
