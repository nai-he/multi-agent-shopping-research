"""商品数据模型"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime

@dataclass
class Review:
    """评价数据模型"""
    username: str
    rating: float  # 1-5 星
    content: str
    date: str
    helpful_count: int = 0
    images: List[str] = field(default_factory=list)
    sentiment_score: Optional[float] = None  # -1 到 1

@dataclass
class Seller:
    """卖家信息模型"""
    name: str
    rating: float  # 1-5 星
    reputation_level: str  # 例如：金冠、皇冠等
    followers: int = 0
    response_rate: Optional[float] = None
    ship_speed_score: Optional[float] = None
    service_score: Optional[float] = None

@dataclass
class Product:
    """商品数据模型"""
    # 基本信息
    product_id: str
    title: str
    price: float
    platform: str  # xianyu, taobao, jd, pdd
    url: str

    # 销售信息
    sales: int = 0
    stock: Optional[int] = None

    # 卖家信息
    seller: Optional[Seller] = None

    # 评价信息
    reviews: List[Review] = field(default_factory=list)
    review_count: int = 0
    positive_rate: float = 0.0

    # 额外信息
    images: List[str] = field(default_factory=list)
    description: str = ""
    tags: List[str] = field(default_factory=list)

    # 元数据
    crawled_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "product_id": self.product_id,
            "title": self.title,
            "price": self.price,
            "platform": self.platform,
            "url": self.url,
            "sales": self.sales,
            "stock": self.stock,
            "seller": {
                "name": self.seller.name if self.seller else "",
                "rating": self.seller.rating if self.seller else 0,
                "reputation_level": self.seller.reputation_level if self.seller else "",
            } if self.seller else None,
            "review_count": self.review_count,
            "positive_rate": self.positive_rate,
            "crawled_at": self.crawled_at
        }

@dataclass
class AnalysisResult:
    """分析结果模型"""
    product: Product
    sentiment_analysis: Dict = field(default_factory=dict)
    negative_keywords: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high
    recommendation_score: float = 0.0
