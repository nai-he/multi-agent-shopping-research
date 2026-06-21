"""为平台创建持久化登录会话。"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent

PLATFORM_HOME_URLS = {
    "xianyu": "https://www.goofish.com/",
    "taobao": "https://www.taobao.com/",
    "jd": "https://www.jd.com/",
    "pdd": "https://mobile.yangkeduo.com/",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="打开可复用的持久化浏览器会话，手动登录一次后供后台抓取复用",
    )
    parser.add_argument(
        "--platform",
        "-p",
        required=True,
        choices=sorted(PLATFORM_HOME_URLS.keys()),
        help="要初始化登录会话的平台",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
        help="打开浏览器后等待的秒数，默认 180 秒",
    )
    return parser


async def bootstrap_session(platform: str, wait_seconds: int) -> None:
    from playwright.async_api import async_playwright

    profile_dir = project_root / "data" / "browser_profiles" / platform
    profile_dir.mkdir(parents=True, exist_ok=True)
    storage_state_path = profile_dir / "storage_state.json"

    print(f"[1/3] 平台: {platform}")
    print(f"[2/3] 会话目录: {profile_dir}")
    print("[3/3] 浏览器已打开，请在这个窗口里手动登录；关闭窗口或等待超时后会自动保存会话快照。")

    async with async_playwright() as playwright:
        launch_kwargs = {
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
            "ignore_default_args": ["--enable-automation"],
            "viewport": {"width": 1366, "height": 900},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
        }
        try:
            context = await playwright.chromium.launch_persistent_context(
                str(profile_dir),
                channel="chrome",
                **launch_kwargs,
            )
        except Exception as chrome_exc:
            print(f"[提示] 系统 Chrome 启动失败，改用 Playwright Chromium: {chrome_exc}")
            try:
                context = await playwright.chromium.launch_persistent_context(
                    str(profile_dir),
                    **launch_kwargs,
                )
            except Exception as profile_exc:
                print(f"[提示] 持久化 Profile 也不可用，改用临时会话窗口: {profile_exc}")
                browser = await playwright.chromium.launch(**launch_kwargs)
                context = await browser.new_context(
                    viewport=launch_kwargs["viewport"],
                    locale=launch_kwargs["locale"],
                    timezone_id=launch_kwargs["timezone_id"],
                )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(PLATFORM_HOME_URLS[platform], wait_until="domcontentloaded")
        await page.wait_for_timeout(wait_seconds * 1000)
        await context.storage_state(path=str(storage_state_path))
        print(f"[完成] 已保存会话快照: {storage_state_path}")
        await context.close()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(bootstrap_session(args.platform, args.wait_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
