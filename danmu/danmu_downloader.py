"""弹幕下载器模块

该模块提供自动弹幕下载功能，根据视频文件名自动搜索和下载对应弹幕。
主要功能：
1. 解析视频文件名，提取剧集信息
2. 搜索匹配的动漫/剧集
3. 获取分集信息
4. 下载弹幕数据
5. 转换为XML格式并保存
"""

import sys
import os
import re
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from danmu.danmu_client import DanmuClient
from danmu.json_to_xml import JsonToXmlConverter
from utils.video_parser import VideoFileParser
from config import DANMU_SOURCES, DEFAULT_SOURCE

# 设置日志
logger = logging.getLogger('danmu_downloader')

class DanmuDownloader:
    """自动弹幕下载器，根据视频文件自动搜索和下载弹幕
    
    该类提供完整的弹幕下载流程，包括视频文件解析、动漫搜索、分集匹配和弹幕下载等功能。
    支持多个弹幕源，可以同时下载多个源的弹幕数据。
    
    Attributes:
        config: 配置字典，包含API密钥等设置
        danmu_client: 弹幕API客户端
        xml_converter: JSON到XML的转换器
        video_parser: 视频文件解析器
        danmu_sources: 支持的弹幕源列表
        default_source: 默认弹幕源
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化弹幕下载器
        
        Args:
            config: 配置字典，包含API密钥等设置
        """
        self.config = config or {}
        self.danmu_client = DanmuClient()
        self.xml_converter = JsonToXmlConverter()
        self.video_parser = VideoFileParser()
        
        # 如果配置中有API key，设置到客户端
        danmu_api_config = self.config.get('danmu_api', {})
        api_key = danmu_api_config.get('token', '')
        if api_key:
            self.danmu_client.set_token(api_key)
        
        # 弹幕源配置
        self.danmu_sources = DANMU_SOURCES
        
        # 默认使用爱奇艺作为弹幕源
        self.default_source = DEFAULT_SOURCE
    
    async def process_video_file(self, video_filepath: str) -> Dict[str, Any]:
        """
        处理单个视频文件，自动下载对应弹幕
        
        完整的处理流程包括：
        1. 解析视频文件名，提取剧集信息
        2. 搜索匹配的动漫/剧集
        3. 获取分集信息
        4. 下载弹幕数据
        5. 转换为XML格式并保存
        
        Args:
            video_filepath: 视频文件路径
            
        Returns:
            Dict[str, Any]: 处理结果，包含以下字段：
                - success: 是否成功
                - message: 处理结果消息
                - video_file: 视频文件路径
                - downloaded_files: 下载的弹幕文件列表（成功时）
                - failed_sources: 失败的弹幕源列表（如果有）
                - series_name: 剧集名称（成功时）
                - episode: 集数（成功时）
                - danmu_count: 弹幕数量（成功时）
        """
        try:
            logger.info(f"开始处理视频文件: {video_filepath}")
            
            # 1. 解析视频文件名
            video_info = self.video_parser.parse_video_filename(video_filepath)
            if not video_info:
                return {
                    'success': False,
                    'message': '无法解析视频文件名',
                    'video_file': video_filepath
                }
            
            logger.info(f"视频解析结果: {video_info}")
            
            # 2. 获取弹幕文件路径（强制覆盖模式）
            danmu_filepath = self.video_parser.get_danmu_filepath(
                video_info, 
                self.danmu_sources[self.default_source]
            )

            if os.path.exists(danmu_filepath):
                logger.info(f"弹幕文件已存在，将强制覆盖: {danmu_filepath}")

            # 3. 搜索动漫/剧集（传递季数信息）
            search_result = self._search_anime(video_info['series_name'], video_info.get('season'))
            if not search_result:
                return {
                    'success': False,
                    'message': f"未找到匹配的动漫: {video_info['series_name']} 第{video_info.get('season', '?')}季",
                    'video_file': video_filepath
                }
            
            # 4. 获取分集信息
            all_episodes = self._get_episodes(search_result['animeId'])
            if not all_episodes:
                return {
                    'success': False,
                    'message': '未找到分集信息',
                    'video_file': video_filepath
                }
            
            # 5. 为每个源下载弹幕
            downloaded_files = []
            failed_sources = []
            
            for provider_name, episodes in all_episodes.items():
                try:
                    logger.info(f"处理弹幕源: {provider_name}")
                    
                    # 匹配对应集数
                    target_episode = self._match_episode(episodes, video_info['episode'])
                    if not target_episode:
                        logger.warning(f"{provider_name} 未找到第{video_info['episode']}集")
                        failed_sources.append(f"{provider_name}: 未找到对应集数")
                        continue
                    
                    # 下载弹幕
                    danmu_data = self._download_danmu(target_episode['episodeId'])
                    if not danmu_data:
                        logger.warning(f"{provider_name} 弹幕下载失败")
                        failed_sources.append(f"{provider_name}: 弹幕下载失败")
                        continue
                    
                    # 根据providerName更新弹幕文件路径
                    danmu_filepath = self._get_correct_danmu_filepath(video_info, provider_name, video_filepath)
                    
                    # 转换为XML并保存，使用ID格式的provider名称
                    xml_provider_name = DANMU_SOURCES.get(provider_name.lower(), f"{provider_name.capitalize()}ID")
                    xml_result = self._save_danmu_xml(danmu_data, danmu_filepath, xml_provider_name)
                    if not xml_result:
                        logger.warning(f"{provider_name} XML文件保存失败")
                        failed_sources.append(f"{provider_name}: XML保存失败")
                        continue
                    
                    downloaded_files.append({
                        'provider': provider_name,
                        'file_path': danmu_filepath,
                        'danmu_count': danmu_data.get('count', 0) if isinstance(danmu_data, dict) else 0
                    })
                    logger.info(f"{provider_name} 弹幕处理完成: {danmu_filepath}")
                    
                except Exception as e:
                    logger.error(f"处理 {provider_name} 时出错: {e}")
                    failed_sources.append(f"{provider_name}: {str(e)}")
            
            # 6. 返回结果
            if downloaded_files:
                success_message = f"成功下载 {len(downloaded_files)} 个弹幕源"
                if failed_sources:
                    success_message += f"，失败 {len(failed_sources)} 个源"
                
                # 计算总弹幕数量
                total_danmu_count = sum(file_info.get('danmu_count', 0) for file_info in downloaded_files)
                
                return {
                    'success': True,
                    'message': success_message,
                    'video_file': video_filepath,
                    'downloaded_files': downloaded_files,
                    'failed_sources': failed_sources,
                    'series_name': video_info['series_name'],
                    'episode': video_info['episode'],
                    'danmu_count': total_danmu_count
                }
            else:
                return {
                    'success': False,
                    'message': f"所有弹幕源下载失败: {'; '.join(failed_sources)}",
                    'video_file': video_filepath,
                    'failed_sources': failed_sources
                }
            
        except Exception as e:
            logger.error(f"处理视频文件时出错: {video_filepath}, 错误: {e}")
            return {
                'success': False,
                'message': f'处理失败: {str(e)}',
                'video_file': video_filepath
            }
    
    def _search_anime(self, series_name: str, season: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        搜索动漫/剧集（使用新版API，支持季数匹配）
        
        根据剧集名称搜索匹配的动漫/剧集，支持季数精确匹配。
        
        Args:
            series_name: 剧集名称
            season: 季数（可选，如果提供则精确匹配季数）
            
        Returns:
            Optional[Dict[str, Any]]: 搜索结果或None（未找到匹配时）
        """
        try:
            logger.info(f"搜索动漫: {series_name}, 季数: {season}")
            
            # 使用新版API获取作品列表
            library_result = self.danmu_client.get_library_list()
            if not library_result.get('success'):
                logger.warning(f"获取作品列表失败")
                return None
            
            animes = library_result.get('animes', [])
            
            # 查找匹配的作品（支持模糊匹配和季数匹配）
            matched_animes = []
            for anime in animes:
                anime_title = anime.get('title', '')
                anime_season = anime.get('season', 1)
                
                # 标题匹配
                if series_name.lower() in anime_title.lower() or anime_title.lower() in series_name.lower():
                    matched_animes.append(anime)
                    logger.info(f"找到匹配动漫: {anime_title}, 第{anime_season}季, ID: {anime.get('animeId')}")
            
            if not matched_animes:
                logger.warning(f"搜索无结果: {series_name}")
                return None
            
            # 如果指定了季数，优先匹配对应季数
            if season is not None:
                for anime in matched_animes:
                    if anime.get('season', 1) == season:
                        logger.info(f"精确匹配到第{season}季: {anime.get('title')}")
                        return anime
                logger.warning(f"未找到第{season}季，使用第一个匹配结果")
            
            # 返回第一个匹配的作品
            selected_anime = matched_animes[0]
            logger.info(f"选择动漫: {selected_anime.get('title')}, 第{selected_anime.get('season', 1)}季")
            return selected_anime
            
        except Exception as e:
            logger.error(f"搜索动漫时出错: {series_name}, 错误: {e}")
            return None
    
    def _get_episodes(self, anime_id):
        """
        获取动漫分集信息（使用新版API）
        
        Args:
            anime_id: 作品ID
            
        Returns:
            dict: 包含所有源的分集信息，格式为 {provider_name: episodes_list}
        """
        try:
            logger.info(f"获取分集信息: {anime_id}")
            
            # 获取弹幕源列表
            sources_result = self.danmu_client.get_anime_sources(anime_id)
            if not sources_result.get('success'):
                logger.warning(f"获取弹幕源失败: {anime_id}")
                return None
            
            sources = sources_result.get('sources', [])
            if not sources:
                logger.warning(f"作品 {anime_id} 没有可用的弹幕源")
                return None
            
            all_episodes = {}
            
            # 遍历所有弹幕源
            for source in sources:
                source_id = source.get('sourceId')
                provider_name = source.get('providerName', 'unknown')
                logger.info(f"获取弹幕源: {provider_name} (ID: {source_id})")
                
                # 获取该源的分集列表
                episodes_result = self.danmu_client.get_source_episodes(source_id)
                if not episodes_result.get('success'):
                    logger.warning(f"获取分集列表失败: {source_id}")
                    continue
                
                episodes = episodes_result.get('episodes', [])
                if episodes:
                    # 为每个分集添加providerName信息
                    for episode in episodes:
                        episode['providerName'] = provider_name
                    
                    all_episodes[provider_name] = episodes
                    logger.info(f"{provider_name} 找到 {len(episodes)} 集")
            
            if all_episodes:
                logger.info(f"总共获取到 {len(all_episodes)} 个弹幕源的数据")
                return all_episodes
            else:
                logger.warning(f"作品 {anime_id} 没有获取到任何有效的分集数据")
                return None
            
        except Exception as e:
            logger.error(f"获取分集信息时出错: {anime_id}, 错误: {e}")
            return None
    
    def _match_episode(self, episodes, target_episode_num):
        """
        匹配目标集数
        
        Args:
            episodes: 分集列表
            target_episode_num: 目标集数
            
        Returns:
            dict: 匹配的分集信息或None
        """
        try:
            logger.info(f"匹配集数: {target_episode_num}")
            
            for episode in episodes:
                episode_title = episode.get('episodeTitle', '')
                
                # 尝试从标题中提取集数
                import re
                
                # 匹配各种集数格式
                patterns = [
                    rf'第\s*{target_episode_num}\s*集',
                    rf'第\s*{target_episode_num:02d}\s*集',
                    rf'EP\s*{target_episode_num:02d}',
                    rf'EP\s*{target_episode_num}',
                    rf'\b{target_episode_num:02d}\b',
                    rf'\b{target_episode_num}\b'
                ]
                
                for pattern in patterns:
                    if re.search(pattern, episode_title, re.IGNORECASE):
                        logger.info(f"匹配到集数: {episode_title}")
                        return episode
            
            # 如果按标题匹配失败，尝试按索引匹配（从1开始）
            if 1 <= target_episode_num <= len(episodes):
                episode = episodes[target_episode_num - 1]
                logger.info(f"按索引匹配到集数: {episode.get('episodeTitle', 'Unknown')}")
                return episode
            
            logger.warning(f"未找到匹配的集数: {target_episode_num}")
            return None
            
        except Exception as e:
            logger.error(f"匹配集数时出错: {target_episode_num}, 错误: {e}")
            return None
    
    def _download_danmu(self, episode_id):
        """
        下载弹幕数据（使用新版API）
        
        Args:
            episode_id: 分集ID
            
        Returns:
            dict: 弹幕数据或None
        """
        try:
            logger.info(f"下载弹幕: {episode_id}")
            
            # 使用新版API下载弹幕
            danmu_result = self.danmu_client.get_episode_danmaku(str(episode_id))
            
            if not danmu_result.get('success'):
                logger.warning(f"弹幕下载失败: {episode_id}")
                return None
            
            danmu_data = danmu_result.get('danmaku')
            if danmu_data:
                comment_count = danmu_data.get('count', 0)
                logger.info(f"下载到 {comment_count} 条弹幕")
            
            return danmu_data
            
        except Exception as e:
            logger.error(f"下载弹幕时出错: {episode_id}, 错误: {e}")
            return None
    
    def _save_danmu_xml(self, danmu_data, output_filepath, provider_name):
        """
        将弹幕数据转换为XML并保存
        
        Args:
            danmu_data: 弹幕数据
            output_filepath: 输出文件路径
            provider_name: 弹幕源名称
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info(f"保存弹幕XML: {output_filepath}")
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_filepath)
            os.makedirs(output_dir, exist_ok=True)
            
            # 提取弹幕列表
            comments = danmu_data.get('comments', []) if isinstance(danmu_data, dict) else danmu_data
            
            # 转换为XML，使用实际的provider_name
            success = self.xml_converter.convert_json_to_xml(
                comments, 
                output_filepath,
                use_dandan_format=True,
                provider_name=provider_name
            )
            
            if success:
                logger.info(f"XML文件保存成功: {output_filepath}")
                return True
            else:
                logger.error(f"XML文件保存失败: {output_filepath}")
                return False
                
        except Exception as e:
            logger.error(f"保存弹幕XML时出错: {output_filepath}, 错误: {e}")
            return False
    
    def _get_correct_danmu_filepath(self, video_info, provider_name, video_filepath=None):
        """
        根据providerName生成正确的弹幕文件路径
        
        Args:
            video_info: 视频信息
            provider_name: 弹幕源名称
            video_filepath: 原始视频文件路径
            
        Returns:
            str: 弹幕文件路径
        """
        # 获取对应的后缀，使用公共配置
        suffix = DANMU_SOURCES.get(provider_name.lower(), f"{provider_name.capitalize()}ID")
        
        # 生成文件名
        base_name = f"{video_info['series_name']} - S{video_info['season']:02d}E{video_info['episode']} - 第 {video_info['episode']} 集_{suffix}.xml"
        
        # 确定输出目录
        if video_filepath:
            output_dir = os.path.dirname(os.path.abspath(video_filepath))
        else:
            output_dir = os.path.dirname(video_info.get('filepath', '.'))
            if not output_dir or output_dir == '':
                output_dir = '.'
        
        # 返回完整路径
        return os.path.join(output_dir, base_name)
    



# 测试函数
async def test_downloader():
    """测试弹幕下载功能"""
    downloader = DanmuDownloader()
    
    # 测试文件 - 使用test_videos目录中的实际文件
    test_video_path = os.path.join("test_videos", "沧元图 - S01E14 - 第 14 集.mp4")
    
    print(f"测试弹幕下载: {test_video_path}")
    result = await downloader.process_video_file(test_video_path)
    
    print(f"处理结果: {result}")


if __name__ == "__main__":
    asyncio.run(test_downloader())