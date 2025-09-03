#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
弹幕API客户端
用于请求弹幕JSON数据的工具类
"""

import json
import logging
import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin


class DanmuClient:
    """弹幕API客户端类"""
    
    # 硬编码的接口路径
    SEARCH_ENDPOINT = "/api/v2/search/anime"
    BANGUMI_ENDPOINT = "/api/v2/bangumi"
    COMMENT_ENDPOINT = "/comment"
    
    def __init__(self, config_path: str = "config.json", base_url: str = None):
        """初始化弹幕客户端
        
        Args:
            config_path: 配置文件路径
            base_url: 可选的base_url，如果提供则覆盖配置文件中的设置
        """
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        if base_url:
            self.config['base_url'] = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DanmuClient/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            配置字典
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get('danmu_api', {})
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            raise
    
    def set_base_url(self, base_url: str) -> None:
        """设置base_url
        
        Args:
            base_url: 新的base_url
        """
        self.config['base_url'] = base_url
        self.logger.info(f"已更新base_url: {base_url}")
    
    def get_base_url(self) -> str:
        """获取当前的base_url
        
        Returns:
            当前的base_url
        """
        return self.config.get('base_url', '')
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """发送HTTP请求
        
        Args:
            url: 请求URL
            params: 请求参数
            
        Returns:
            响应JSON数据
        """
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求失败: {url}, 错误: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            raise
    
    def search_anime(self, keyword: str) -> Dict[str, Any]:
        """搜索动漫
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            搜索结果，包含animes列表
        """
        base_url = self.config.get('base_url', '')
        
        if not base_url:
            raise ValueError("配置文件中缺少base_url")
        
        url = base_url + self.SEARCH_ENDPOINT
        params = {'keyword': keyword}
        
        self.logger.info(f"搜索动漫: {keyword}")
        result = self._make_request(url, params)
        
        if result.get('success'):
            animes = result.get('animes', [])
            self.logger.info(f"搜索到 {len(animes)} 个结果")
        else:
            error_msg = result.get('errorMessage', '未知错误')
            self.logger.error(f"搜索失败: {error_msg}")
        
        return result
    
    def get_bangumi_details(self, bangumi_id: str) -> Dict[str, Any]:
        """获取番剧详情和分集信息
        
        Args:
            bangumi_id: 番剧ID (如: A40)
            
        Returns:
            番剧详情，包含episodes列表
        """
        base_url = self.config.get('base_url', '')
        
        if not base_url:
            raise ValueError("配置文件中缺少base_url")
        
        url = base_url + f"{self.BANGUMI_ENDPOINT}/{bangumi_id}"
        
        self.logger.info(f"获取番剧详情: {bangumi_id}")
        result = self._make_request(url)
        
        if result.get('success'):
            bangumi = result.get('bangumi', {})
            if bangumi:
                episodes = bangumi.get('episodes', [])
                self.logger.info(f"获取到 {len(episodes)} 集")
            else:
                self.logger.warning("番剧详情为空")
        else:
            error_msg = result.get('errorMessage', '未知错误')
            self.logger.error(f"获取番剧详情失败: {error_msg}")
        
        return result
    
    def get_episode_comments(self, episode_id: int) -> Dict[str, Any]:
        """获取分集弹幕数据
        
        Args:
            episode_id: 分集ID
            
        Returns:
            弹幕JSON数据
        """
        base_url = self.config.get('base_url', '')
        
        if not base_url:
            raise ValueError("配置文件中缺少base_url")
        
        url = base_url + f"{self.COMMENT_ENDPOINT}/{episode_id}"
        
        self.logger.info(f"获取分集弹幕: {episode_id}")
        result = self._make_request(url)
        
        # 弹幕接口可能直接返回弹幕数据，不一定有success字段
        if isinstance(result, dict) and 'comments' in result:
            comments = result.get('comments', [])
            self.logger.info(f"获取到 {len(comments)} 条弹幕")
        elif isinstance(result, list):
            self.logger.info(f"获取到 {len(result)} 条弹幕")
        
        return result
    
    def search_and_get_episodes(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索动漫并获取所有相关分集信息
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            所有匹配动漫的分集信息列表
        """
        all_episodes = []
        
        # 1. 搜索动漫
        search_result = self.search_anime(keyword)
        if not search_result.get('success'):
            return all_episodes
        
        animes = search_result.get('animes', [])
        
        # 2. 遍历每个动漫，获取分集信息
        for anime in animes:
            bangumi_id = anime.get('bangumiId')
            if not bangumi_id:
                continue
            
            try:
                bangumi_result = self.get_bangumi_details(bangumi_id)
                if bangumi_result.get('success'):
                    bangumi = bangumi_result.get('bangumi', {})
                    episodes = bangumi.get('episodes', [])
                    
                    # 添加动漫信息到每个分集
                    for episode in episodes:
                        episode['animeInfo'] = {
                            'animeId': anime.get('animeId'),
                            'bangumiId': bangumi_id,
                            'animeTitle': anime.get('animeTitle'),
                            'year': anime.get('year'),
                            'episodeCount': anime.get('episodeCount')
                        }
                    
                    all_episodes.extend(episodes)
            except Exception as e:
                self.logger.error(f"获取番剧 {bangumi_id} 详情失败: {e}")
                continue
        
        return all_episodes
    
    def get_episode_danmu_by_keyword(self, keyword: str, episode_number: str = "1") -> Optional[Dict[str, Any]]:
        """根据关键词和集数获取弹幕数据
        
        Args:
            keyword: 搜索关键词
            episode_number: 集数 (默认第1集)
            
        Returns:
            弹幕数据，如果找不到则返回None
        """
        episodes = self.search_and_get_episodes(keyword)
        
        # 查找指定集数
        target_episode = None
        for episode in episodes:
            if episode.get('episodeNumber') == episode_number:
                target_episode = episode
                break
        
        if not target_episode:
            self.logger.warning(f"未找到关键词 '{keyword}' 的第 {episode_number} 集")
            return None
        
        episode_id = target_episode.get('episodeId')
        if not episode_id:
            self.logger.error("分集ID为空")
            return None
        
        # 获取弹幕数据
        try:
            return self.get_episode_comments(episode_id)
        except Exception as e:
            self.logger.error(f"获取弹幕数据失败: {e}")
            return None


def main():
    """主函数，用于测试"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建客户端
    client = DanmuClient()
    
    # 测试搜索
    keyword = "那年那兔那些事儿"
    print(f"\n=== 搜索动漫: {keyword} ===")
    search_result = client.search_anime(keyword)
    print(json.dumps(search_result, ensure_ascii=False, indent=2))
    
    # 测试获取番剧详情
    if search_result.get('success') and search_result.get('animes'):
        first_anime = search_result['animes'][0]
        bangumi_id = first_anime.get('bangumiId')
        
        if bangumi_id:
            print(f"\n=== 获取番剧详情: {bangumi_id} ===")
            bangumi_result = client.get_bangumi_details(bangumi_id)
            print(json.dumps(bangumi_result, ensure_ascii=False, indent=2))
            
            # 测试获取弹幕
            if bangumi_result.get('success'):
                bangumi = bangumi_result.get('bangumi', {})
                episodes = bangumi.get('episodes', [])
                
                if episodes:
                    first_episode = episodes[0]
                    episode_id = first_episode.get('episodeId')
                    
                    if episode_id:
                        print(f"\n=== 获取弹幕: {episode_id} ===")
                        try:
                            comments_result = client.get_episode_comments(episode_id)
                            print(f"弹幕数据类型: {type(comments_result)}")
                            if isinstance(comments_result, dict):
                                print(f"弹幕数据键: {list(comments_result.keys())}")
                            elif isinstance(comments_result, list):
                                print(f"弹幕数量: {len(comments_result)}")
                        except Exception as e:
                            print(f"获取弹幕失败: {e}")


if __name__ == "__main__":
    main()