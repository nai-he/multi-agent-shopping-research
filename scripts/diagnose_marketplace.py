"""单平台抓取诊断脚本。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "agents" / "scraper-agent"))

from agent import ScraperAgent  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="逐个平台诊断真实抓取状态",
    )
    parser.add_argument(
        "--query",
        "-q",
        required=True,
        help="原始查询，如：100元以下的鞋子",
    )
    parser.add_argument(
        "--platform",
        "-p",
        required=True,
        choices=["xianyu", "taobao", "jd", "pdd"],
        help="要诊断的平台",
    )
    parser.add_argument(
        "--sample-count",
        "-n",
        type=int,
        default=10,
        help="目标抓取数量，默认 10",
    )
    parser.add_argument(
        "--location",
        "-l",
        default="",
        help="地区过滤，如 福建/厦门",
    )
    parser.add_argument(
        "--sort-order",
        choices=["none", "price_asc", "price_desc"],
        default="none",
        help="价格排序方式",
    )
    parser.add_argument(
        "--budget-min",
        type=float,
        default=None,
        help="最低预算，可选",
    )
    parser.add_argument(
        "--budget-max",
        type=float,
        default=None,
        help="最高预算，可选",
    )
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=None,
        help="可选的 AI 扩展关键词，用空格分隔",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    agent = ScraperAgent()
    products = agent.fetch_products(
        query=args.query,
        platforms=[args.platform],
        max_results_per_platform=max(1, args.sample_count),
        location=args.location,
        sort_order=args.sort_order,
        search_keywords=args.keywords,
        budget_min=args.budget_min,
        budget_max=args.budget_max,
    )

    platform_meta = (
        agent.last_crawl_meta.get("platforms", {}).get(args.platform, {}) or {}
    )
    payload = {
        "query": args.query,
        "platform": args.platform,
        "products_count": len(products),
        "query_plan": agent.last_crawl_meta.get("query_plan", {}),
        "platform_meta": platform_meta,
        "suggested_next_action": platform_meta.get("suggested_next_action", ""),
        "sample_products": [
            {
                "title": product.title,
                "price": product.price,
                "platform": product.platform,
                "url": product.url,
            }
            for product in products[:5]
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    print(text.encode("utf-8", errors="replace").decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
