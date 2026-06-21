"""爬虫基类"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class BaseScraper(ABC):
    """爬虫基类"""

    def __init__(self, headless: bool = True):
        """初始化爬虫"""
        self.headless = headless
        self.driver = None

    def _init_driver(self):
        """初始化浏览器驱动"""
        if self.driver:
            return

        options = Options()
        if self.headless:
            options.add_argument('--headless')

        # 反爬虫设置
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # 禁用 GPU 和沙箱（解决 Windows 兼容性问题）
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        try:
            # 方法1: 尝试使用 webdriver-manager（会使用缓存）
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                import os
                os.environ['WDM_SSL_VERIFY'] = '0'  # 禁用 SSL 验证

                self.driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=options
                )
            except:
                # 方法2: 如果 webdriver-manager 失败，尝试使用系统 PATH 中的 chromedriver
                self.driver = webdriver.Chrome(options=options)

            # 设置反爬脚本
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })

        except Exception as e:
            raise RuntimeError(
                f"Chrome 驱动初始化失败: {str(e)}\n"
                f"请确保:\n"
                f"1. 已安装 Chrome 浏览器\n"
                f"2. 网络正常或已有缓存的 ChromeDriver"
            )

    def _random_sleep(self, min_sec: float = 1, max_sec: float = 3):
        """随机延时，模拟人类行为"""
        time.sleep(random.uniform(min_sec, max_sec))

    def _safe_find_element(self, by, value, timeout=10):
        """安全查找元素"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            return None

    def _safe_find_elements(self, by, value, timeout=10):
        """安全查找多个元素"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return self.driver.find_elements(by, value)
        except TimeoutException:
            return []

    @abstractmethod
    def search(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        搜索商品

        Args:
            query: 搜索关键词
            max_results: 最大结果数量

        Returns:
            商品数据列表
        """
        pass

    @abstractmethod
    def parse_product(self, element) -> Dict[str, Any]:
        """
        解析单个商品元素

        Args:
            element: 商品元素

        Returns:
            商品数据字典
        """
        pass

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __enter__(self):
        """上下文管理器入口"""
        self._init_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
