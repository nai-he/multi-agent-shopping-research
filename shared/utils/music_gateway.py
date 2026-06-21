"""
音乐网关 API 客户端
支持 QQ 音乐和网易云音乐的搜索、获取歌曲信息等
"""
import requests
from typing import Optional, Dict, List, Any


class MusicGatewayClient:
    """音乐网关 API 客户端"""

    def __init__(self, api_key: str, base_url: str = "https://gateway.karpov.cn/api"):
        """
        初始化客户端

        Args:
            api_key: API Key
            base_url: API 基础 URL
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            endpoint: API 端点
            **kwargs: requests 参数

        Returns:
            响应数据
        """
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()

        result = response.json()
        if result.get('code') != 0:
            raise Exception(f"API Error: {result.get('message', 'Unknown error')}")

        return result.get('data', {})

    def search_songs(
        self,
        provider: str,
        query: str,
        page: int = 1,
        page_size: int = 20
    ) -> List[Dict[str, Any]]:
        """
        搜索歌曲

        Args:
            provider: 平台 (qqmusic 或 netease)
            query: 搜索关键词
            page: 页码
            page_size: 每页数量

        Returns:
            歌曲列表
        """
        endpoint = f"/v1/{provider}/search/songs"
        params = {
            'q': query,
            'page': page,
            'page_size': page_size
        }

        data = self._request('GET', endpoint, params=params)
        return data.get('songs', [])

    def get_song_detail(self, provider: str, song_id: str) -> Dict[str, Any]:
        """
        获取歌曲详情

        Args:
            provider: 平台 (qqmusic 或 netease)
            song_id: 歌曲 ID

        Returns:
            歌曲详情
        """
        endpoint = f"/v1/{provider}/songs/{song_id}"
        return self._request('GET', endpoint)

    def get_song_url(
        self,
        provider: str,
        song_id: str,
        quality: str = 'MP3_320'
    ) -> Dict[str, Any]:
        """
        获取歌曲播放链接

        Args:
            provider: 平台 (qqmusic 或 netease)
            song_id: 歌曲 ID
            quality: 音质 (MP3_128, MP3_320, FLAC 等)

        Returns:
            包含播放链接的字典
        """
        endpoint = f"/v1/{provider}/songs/{song_id}/url"
        params = {'quality': quality}
        return self._request('GET', endpoint, params=params)

    def get_song_lyric(self, provider: str, song_id: str) -> Dict[str, Any]:
        """
        获取歌词

        Args:
            provider: 平台 (qqmusic 或 netease)
            song_id: 歌曲 ID

        Returns:
            歌词数据
        """
        endpoint = f"/v1/{provider}/songs/{song_id}/lyric"
        return self._request('GET', endpoint)

    def get_album(self, provider: str, album_id: str) -> Dict[str, Any]:
        """
        获取专辑信息

        Args:
            provider: 平台 (qqmusic 或 netease)
            album_id: 专辑 ID

        Returns:
            专辑信息
        """
        endpoint = f"/v1/{provider}/albums/{album_id}"
        return self._request('GET', endpoint)

    def get_artist(self, provider: str, artist_id: str) -> Dict[str, Any]:
        """
        获取歌手信息

        Args:
            provider: 平台 (qqmusic 或 netease)
            artist_id: 歌手 ID

        Returns:
            歌手信息
        """
        endpoint = f"/v1/{provider}/artists/{artist_id}"
        return self._request('GET', endpoint)

    def get_playlist(self, provider: str, playlist_id: str) -> Dict[str, Any]:
        """
        获取歌单信息

        Args:
            provider: 平台 (qqmusic 或 netease)
            playlist_id: 歌单 ID

        Returns:
            歌单信息
        """
        endpoint = f"/v1/{provider}/playlists/{playlist_id}"
        return self._request('GET', endpoint)
