"""Claude API 客户端工具类"""
import json
import requests
from typing import Dict, Any, Optional
import time
from urllib.parse import urlparse

class ClaudeAPIClient:
    """Claude API 客户端，用于与 New API 聚合网关通信"""

    def __init__(self, api_key: str, base_url: str, model: str = "claude-opus-4-7"):
        self.api_key = api_key
        self.base_url = self._normalize_base_url(base_url)
        self.model = model
        self.session = requests.Session()

    def _normalize_base_url(self, base_url: str) -> str:
        """Normalize Anthropic-compatible base URLs to a messages endpoint."""
        if not base_url:
            return base_url

        normalized = base_url.rstrip("/")
        path = urlparse(normalized).path.rstrip("/")

        if path.endswith("/messages"):
            return normalized
        if path.endswith("/v1"):
            return f"{normalized}/messages"

        return f"{normalized}/v1/messages"

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    def send_message(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0
    ) -> Dict[str, Any]:
        """
        发送消息到 Claude API

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            max_tokens: 最大生成 token 数
            temperature: 温度参数

        Returns:
            API 响应结果
        """
        # 构建消息体
        messages = [{"role": "user", "content": prompt}]

        request_body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "stream": False
        }

        # 如果有系统提示词，添加到请求中
        if system_prompt:
            request_body["system"] = system_prompt

        try:
            # 发送请求
            response = self.session.post(
                self.base_url,
                headers=self._build_headers(),
                json=request_body,
                timeout=60
            )

            # 检查响应状态
            if response.status_code == 200:
                result = response.json()
                # 提取文本内容 — 兼容 thinking + text 多 block 格式
                if "content" in result and len(result["content"]) > 0:
                    text_blocks = [
                        b["text"] for b in result["content"]
                        if b.get("type") == "text" and "text" in b
                    ]
                    result["text"] = text_blocks[0] if text_blocks else ""
                return result
            elif response.status_code == 401:
                raise Exception("API Key 无效或已过期")
            elif response.status_code == 503:
                raise Exception("服务暂时不可用，请稍后重试")
            else:
                raise Exception(f"API 错误 {response.status_code}: {response.text}")

        except requests.exceptions.Timeout:
            raise Exception("API 请求超时")
        except requests.exceptions.ConnectionError:
            raise Exception("无法连接到 API 服务器")
        except Exception as e:
            raise Exception(f"API 调用失败: {str(e)}")

    def send_message_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """带重试机制的消息发送"""
        last_error = None

        for attempt in range(max_retries):
            try:
                return self.send_message(prompt, system_prompt, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 指数退避
                    print(f"第 {attempt + 1} 次尝试失败，{wait_time} 秒后重试...")
                    time.sleep(wait_time)

        raise Exception(f"重试 {max_retries} 次后仍然失败: {str(last_error)}")
