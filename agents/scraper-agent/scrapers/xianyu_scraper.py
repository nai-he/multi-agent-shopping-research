"""闲鱼爬虫"""
from typing import List, Dict, Any
import re
from selenium.webdriver.common.by import By
from .base_scraper import BaseScraper


class XianyuScraper(BaseScraper):
    """闲鱼商品爬虫"""

    BASE_URL = "https://2.taobao.com"

    def search(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        搜索闲鱼商品

        Args:
            query: 搜索关键词
            max_results: 最大结果数量

        Returns:
            商品数据列表
        """
        self._init_driver()

        # 构建搜索 URL
        search_url = f"https://s.2.taobao.com/list/list.htm?q={query}"
        self.driver.get(search_url)
        self._random_sleep(2, 4)

        products = []
        page = 1

        while len(products) < max_results and page <= 5:  # 最多爬5页
            # 查找商品列表
            product_elements = self._safe_find_elements(
                By.CSS_SELECTOR,
                ".item-card, .card-item, [class*='item']",
                timeout=10
            )

            if not product_elements:
                print(f"第 {page} 页未找到商品元素")
                break

            # 解析每个商品
            for element in product_elements:
                if len(products) >= max_results:
                    break

                try:
                    product = self.parse_product(element)
                    if product:
                        products.append(product)
                except Exception as e:
                    print(f"解析商品失败: {str(e)}")
                    continue

            # 翻页
            page += 1
            if len(products) < max_results:
                self._try_next_page()
                self._random_sleep(2, 4)

        return products[:max_results]

    def parse_product(self, element) -> Dict[str, Any]:
        """解析单个商品元素"""
        try:
            # 标题
            title_elem = element.find_element(By.CSS_SELECTOR, ".title, [class*='title']")
            title = title_elem.text.strip() if title_elem else ""

            # 价格
            price_elem = element.find_element(By.CSS_SELECTOR, ".price, [class*='price']")
            price_text = price_elem.text.strip() if price_elem else "0"
            price = self._extract_price(price_text)

            # 链接
            link_elem = element.find_element(By.TAG_NAME, "a")
            url = link_elem.get_attribute("href") if link_elem else ""

            # 图片
            img_elem = element.find_element(By.TAG_NAME, "img")
            image = img_elem.get_attribute("src") if img_elem else ""

            # 卖家信息
            seller_elem = element.find_elements(By.CSS_SELECTOR, ".seller, [class*='seller']")
            seller_name = seller_elem[0].text.strip() if seller_elem else "未知卖家"

            if not title or price <= 0:
                return None

            return {
                "title": title,
                "price": price,
                "url": url,
                "image": image,
                "seller_name": seller_name,
                "platform": "xianyu"
            }

        except Exception as e:
            return None

    def _extract_price(self, price_text: str) -> float:
        """从文本中提取价格"""
        try:
            # 移除非数字字符，保留小数点
            price_str = re.sub(r'[^\d.]', '', price_text)
            return float(price_str) if price_str else 0.0
        except:
            return 0.0

    def _try_next_page(self):
        """尝试翻页"""
        try:
            next_button = self.driver.find_element(
                By.CSS_SELECTOR,
                ".next, [class*='next'], .pagination-next"
            )
            next_button.click()
            return True
        except:
            return False
