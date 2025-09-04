#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
弹幕API客户端
用于请求弹幕JSON数据的工具类
"""

import json
import logging
import requests
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin


class DanmuClient:
    """弹幕API客户端类
    
    支持缓存机制，避免重复请求相同的数据：
    - 作品列表缓存（默认5分钟有效期）
    - 弹幕源缓存（默认10分钟有效期）
    - 分集列表缓存（默认10分钟有效期）
    """
    
    # 新版API接口路径
    LIBRARY_ENDPOINT = "/api/control/library"  # 获取作品列表
    ANIME_SOURCES_ENDPOINT = "/api/control/library/anime"  # 获取作品弹幕源
    SOURCE_EPISODES_ENDPOINT = "/api/control/library/source"  # 获取源下分集列表
    DANMAKU_ENDPOINT = "/api/control/danmaku"  # 获取弹幕数据
    
    # 缓存配置
    LIBRARY_CACHE_TTL = 300  # 作品列表缓存5分钟
    SOURCES_CACHE_TTL = 600  # 弹幕源缓存10分钟
    EPISODES_CACHE_TTL = 600  # 分集列表缓存10分钟
    
    def __init__(self, config_path: str = "config/config.json", base_url: str = None):
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
        
        # 设置API Key认证
        self.api_key = self.config.get('token', '')
        
        # 初始化缓存
        self._library_cache = {'data': None, 'timestamp': 0}
        self._sources_cache = {}  # {anime_id: {'data': sources, 'timestamp': timestamp}}
        self._episodes_cache = {}  # {source_id: {'data': episodes, 'timestamp': timestamp}}
    
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
    
    def set_token(self, token: str) -> None:
        """设置API访问token
        
        Args:
            token: API访问token
        """
        self.config['token'] = token
        self.api_key = token
        self.logger.info(f"已更新API Key: {'已设置' if token else '已清除'}")
    
    def get_token(self) -> str:
        """获取当前的token
        
        Returns:
            当前的token
        """
        return self.config.get('token', '')
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """发送HTTP请求
        
        Args:
            url: 请求URL
            params: 请求参数
            
        Returns:
            响应JSON数据
        """
        try:
            # 添加API Key到请求参数
            if params is None:
                params = {}
            if self.api_key:
                params['api_key'] = self.api_key
                
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求失败: {url}, 错误: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            raise
    

    
    # ===== 新版API方法 (基于提供的四个接口) =====
    
    def get_library_list(self) -> Dict[str, Any]:
        """获取当前弹幕库中所有已收录的作品列表
        
        Returns:
            作品列表，包含animeId、title、season等信息
        """
        # 优先使用danmu_api.base_url，然后是根级别的base_url
        danmu_config = self.config.get('danmu_api', {})
        base_url = danmu_config.get('base_url') or self.config.get('base_url', '')
        
        if not base_url:
            raise ValueError("配置文件中缺少base_url (请在danmu_api.base_url或base_url中配置)")
        
        url = base_url + self.LIBRARY_ENDPOINT
        
        self.logger.info("获取弹幕库作品列表")
        result = self._make_request(url)
        
        if isinstance(result, list):
            self.logger.info(f"获取到 {len(result)} 个作品")
            return {'success': True, 'animes': result}
        else:
            self.logger.error(f"获取作品列表失败: {result}")
            return {'success': False, 'error': result}
    
    def get_anime_sources(self, anime_id: int) -> Dict[str, Any]:
        """获取指定作品已关联的所有弹幕源列表
        
        Args:
            anime_id: 作品ID
            
        Returns:
            弹幕源列表，包含sourceId、providerName等信息
        """
        # 优先使用danmu_api.base_url，然后是根级别的base_url
        danmu_config = self.config.get('danmu_api', {})
        base_url = danmu_config.get('base_url') or self.config.get('base_url', '')
        
        if not base_url:
            raise ValueError("配置文件中缺少base_url (请在danmu_api.base_url或base_url中配置)")
        
        url = base_url + f"{self.ANIME_SOURCES_ENDPOINT}/{anime_id}/sources"
        
        self.logger.info(f"获取作品 {anime_id} 的弹幕源列表")
        result = self._make_request(url)
        
        if isinstance(result, list):
            self.logger.info(f"获取到 {len(result)} 个弹幕源")
            return {'success': True, 'sources': result}
        else:
            self.logger.error(f"获取弹幕源失败: {result}")
            return {'success': False, 'error': result}
    
    def get_source_episodes(self, source_id: int) -> Dict[str, Any]:
        """获取指定数据源下所有已收录的分集列表
        
        Args:
            source_id: 数据源ID
            
        Returns:
            分集列表，包含episodeId、title、episodeIndex等信息
        """
        # 优先使用danmu_api.base_url，然后是根级别的base_url
        danmu_config = self.config.get('danmu_api', {})
        base_url = danmu_config.get('base_url') or self.config.get('base_url', '')
        
        if not base_url:
            raise ValueError("配置文件中缺少base_url (请在danmu_api.base_url或base_url中配置)")
        
        url = base_url + f"{self.SOURCE_EPISODES_ENDPOINT}/{source_id}/episodes"
        
        self.logger.info(f"获取数据源 {source_id} 的分集列表")
        result = self._make_request(url)
        
        if isinstance(result, list):
            self.logger.info(f"获取到 {len(result)} 个分集")
            return {'success': True, 'episodes': result}
        else:
            self.logger.error(f"获取分集列表失败: {result}")
            return {'success': False, 'error': result}
    
    def get_episode_danmaku(self, episode_id: str) -> Dict[str, Any]:
        """获取对应集数的JSON弹幕数据
        
        Args:
            episode_id: 分集ID
            
        Returns:
            弹幕数据，包含count和comments列表
        """
        # 优先使用danmu_api.base_url，然后是根级别的base_url
        danmu_config = self.config.get('danmu_api', {})
        base_url = danmu_config.get('base_url') or self.config.get('base_url', '')
        
        if not base_url:
            raise ValueError("配置文件中缺少base_url (请在danmu_api.base_url或base_url中配置)")
        
        url = base_url + f"{self.DANMAKU_ENDPOINT}/{episode_id}"
        
        self.logger.info(f"获取分集 {episode_id} 的弹幕数据")
        result = self._make_request(url)
        
        if isinstance(result, dict) and 'count' in result:
            comment_count = result.get('count', 0)
            self.logger.info(f"获取到 {comment_count} 条弹幕")
            return {'success': True, 'danmaku': result}
        else:
            self.logger.error(f"获取弹幕数据失败: {result}")
            return {'success': False, 'error': result}
    
    def get_danmaku_by_title_and_episode(self, title: str, season: int = 1, episode_index: int = 1) -> Optional[Dict[str, Any]]:
        """根据作品标题、季数和集数获取弹幕数据 (完整流程)
        
        Args:
            title: 作品标题 (支持模糊匹配)
            season: 季数 (默认第1季)
            episode_index: 集数 (默认第1集)
            
        Returns:
            弹幕数据，如果找不到则返回None
        """
        try:
            # 步骤1: 获取作品列表
            library_result = self.get_library_list()
            if not library_result.get('success'):
                self.logger.error("获取作品列表失败")
                return None
            
            # 步骤2: 查找匹配的作品
            target_anime = None
            animes = library_result.get('animes', [])
            
            for anime in animes:
                anime_title = anime.get('title', '')
                anime_season = anime.get('season', 1)
                
                # 标题匹配 (支持模糊匹配)
                if title.lower() in anime_title.lower() and anime_season == season:
                    target_anime = anime
                    break
            
            if not target_anime:
                self.logger.warning(f"未找到匹配的作品: {title} 第{season}季")
                return None
            
            anime_id = target_anime.get('animeId')
            self.logger.info(f"找到匹配作品: {target_anime.get('title')} (ID: {anime_id})")
            
            # 步骤3: 获取弹幕源列表
            sources_result = self.get_anime_sources(anime_id)
            if not sources_result.get('success'):
                self.logger.error(f"获取作品 {anime_id} 的弹幕源失败")
                return None
            
            sources = sources_result.get('sources', [])
            if not sources:
                self.logger.warning(f"作品 {anime_id} 没有可用的弹幕源")
                return None
            
            # 选择第一个弹幕源 (可以根据需要优化选择逻辑)
            target_source = sources[0]
            source_id = target_source.get('sourceId')
            self.logger.info(f"使用弹幕源: {target_source.get('providerName')} (ID: {source_id})")
            
            # 步骤4: 获取分集列表
            episodes_result = self.get_source_episodes(source_id)
            if not episodes_result.get('success'):
                self.logger.error(f"获取数据源 {source_id} 的分集列表失败")
                return None
            
            # 步骤5: 查找指定集数
            target_episode = None
            episodes = episodes_result.get('episodes', [])
            
            for episode in episodes:
                if episode.get('episodeIndex') == episode_index:
                    target_episode = episode
                    break
            
            if not target_episode:
                self.logger.warning(f"未找到第 {episode_index} 集")
                return None
            
            episode_id = target_episode.get('episodeId')
            self.logger.info(f"找到目标分集: {target_episode.get('title')} (ID: {episode_id})")
            
            # 步骤6: 获取弹幕数据
            danmaku_result = self.get_episode_danmaku(str(episode_id))
            if danmaku_result.get('success'):
                return danmaku_result.get('danmaku')
            else:
                self.logger.error(f"获取分集 {episode_id} 的弹幕数据失败")
                return None
                
        except Exception as e:
            self.logger.error(f"获取弹幕数据过程中发生错误: {e}")
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
    
    # 测试获取作品列表（新版API）
    keyword = "那年那兔那些事儿"
    print(f"\n=== 获取作品列表并搜索: {keyword} ===")
    library_result = client.get_library_list()
    print(f"获取作品列表结果: {library_result.get('success')}")
    
    # 在作品列表中搜索匹配的动漫
    if library_result.get('success'):
        animes = library_result.get('animes', [])
        matched_anime = None
        for anime in animes:
            if keyword.lower() in anime.get('title', '').lower():
                matched_anime = anime
                break
        
        if matched_anime:
            print(f"找到匹配动漫: {matched_anime.get('title')}, ID: {matched_anime.get('animeId')}")
        else:
            print(f"未找到匹配的动漫: {keyword}")
    
    # 测试获取动漫弹幕源（新版API）
    if library_result.get('success') and matched_anime:
        anime_id = matched_anime.get('animeId')
        
        if anime_id:
            print(f"\n=== 获取动漫弹幕源: {anime_id} ===")
            sources_result = client.get_anime_sources(anime_id)
            print(json.dumps(sources_result, ensure_ascii=False, indent=2))
            
            # 测试获取弹幕源
            if sources_result.get('success'):
                sources = sources_result.get('sources', [])
                if sources:
                    first_source = sources[0]
                    source_id = first_source.get('sourceId')
                    
                    print(f"\n=== 获取源分集列表: {source_id} ===")
                    episodes_result = client.get_source_episodes(source_id)
                    print(json.dumps(episodes_result, ensure_ascii=False, indent=2))
                    
                    if episodes_result.get('success'):
                        episodes = episodes_result.get('episodes', [])
                        if episodes:
                            first_episode = episodes[0]
                            episode_id = first_episode.get('episodeId')
                            
                            print(f"\n=== 获取弹幕数据: {episode_id} ===")
                            danmaku_result = client.get_episode_danmaku(str(episode_id))
                            print(json.dumps(danmaku_result, ensure_ascii=False, indent=2))


def test_new_api():
    """测试新版API方法"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    client = DanmuClient()
    
    print("=== 测试新版API方法 ===")
    
    # 测试1: 获取作品列表
    print("\n1. 获取作品列表:")
    library_result = client.get_library_list()
    if library_result.get('success'):
        animes = library_result.get('animes', [])
        print(f"获取到 {len(animes)} 个作品")
        if animes:
            # 显示前3个作品的信息
            for i, anime in enumerate(animes[:3]):
                print(f"  作品{i+1}: {anime.get('title')} (ID: {anime.get('animeId')}, 第{anime.get('season')}季)")
    else:
        print(f"获取失败: {library_result.get('error')}")
    
    # 测试2: 使用完整流程获取弹幕 (使用实际存在的作品)
    test_title = "沧元图" if animes and animes[0].get('title') == "沧元图" else (animes[0].get('title') if animes else "测试作品")
    print(f"\n2. 测试完整流程 - 获取《{test_title}》第1季第1集弹幕:")
    danmaku_data = client.get_danmaku_by_title_and_episode(test_title, season=1, episode_index=1)
    if danmaku_data:
        comment_count = danmaku_data.get('count', 0)
        print(f"成功获取弹幕数据，共 {comment_count} 条弹幕")
        
        # 显示前5条弹幕
        comments = danmaku_data.get('comments', [])
        if comments:
            print("前5条弹幕:")
            for i, comment in enumerate(comments[:5]):
                if isinstance(comment, dict):
                    text = comment.get('text', comment.get('content', str(comment)))
                    time = comment.get('time', comment.get('timestamp', 'N/A'))
                    print(f"  {i+1}. [{time}] {text}")
                else:
                    print(f"  {i+1}. {comment}")
    else:
        print("未能获取到弹幕数据")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    # 可以选择运行原有的main函数或新的测试函数
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test-new":
        test_new_api()
    else:
        main()