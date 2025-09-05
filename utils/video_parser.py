import re
import os
from pathlib import Path
import logging

# 设置日志
logger = logging.getLogger('video_parser')


class VideoFileParser:
    """视频文件名解析器，用于提取剧名和集数信息"""

    def __init__(self):
        # 常见的集数匹配模式
        self.episode_patterns = [
            # S01E14 格式
            r'[Ss](\d+)[Ee](\d+)',
            # 第14集 格式
            r'第\s*(\d+)\s*集',
            # EP14, ep14 格式
            r'[Ee][Pp]\s*(\d+)',
            # 14集 格式
            r'(\d+)\s*集',
            # [14] 格式
            r'\[(\d+)\]',
            # 14话 格式
            r'(\d+)\s*话',
            # 下划线分隔格式，如"剧名_27"或"剧名_27_其他"
            r'_(\d+)(?:_|$)',
            # 纯数字格式（最后匹配，避免误匹配）
            r'\b(\d{1,3})\b'
        ]

        # 需要过滤的关键词（避免误匹配）
        self.filter_keywords = [
            '1080p', '720p', '480p', '4k', '2160p',
            'x264', 'x265', 'h264', 'h265',
            'bluray', 'webrip', 'hdtv', 'dvdrip',
            'aac', 'ac3', 'dts', 'flac',
            'mkv', 'mp4', 'avi', 'mov'
        ]

    def parse_video_filename(self, filepath, content_type=None):
        """
        解析视频文件名，提取剧名、季数、集数等信息

        Args:
            filepath: 视频文件路径
            content_type: 内容类型 ('movie', 'tv_series', None)
                         None表示自动检测

        Returns:
            dict: 包含剧名、季数、集数等信息的字典，解析失败返回None
        """
        try:
            # 获取文件名（不包含路径）
            filename = os.path.basename(filepath)

            # 获取文件目录和扩展名
            file_dir = os.path.dirname(os.path.abspath(
                filepath)) if os.path.dirname(filepath) else os.getcwd()
            filename_without_ext, file_ext = os.path.splitext(filename)

            logger.info(f"解析视频文件: {filename}")
            logger.info(f"文件目录: {file_dir}")

            # 如果指定了具体类型，直接使用对应的解析方法
            if content_type == 'movie':
                return self._parse_movie_filename(filename_without_ext, filename, file_dir, file_ext)
            elif content_type == 'tv_series':
                return self._parse_tv_series_filename(filename_without_ext, filename, file_dir, file_ext)
            
            # 自动检测类型：通过正则匹配优先判断
            detected_type = self._detect_content_type(filename_without_ext)
            logger.debug(f"检测到的内容类型: {detected_type}")
            
            if detected_type == 'movie':
                movie_result = self._parse_movie_filename(filename_without_ext, filename, file_dir, file_ext)
                if movie_result:
                    return movie_result
                # 电影解析失败，尝试电视剧解析作为备选
                logger.debug("电影解析失败，尝试电视剧解析")
                return self._parse_tv_series_filename(filename_without_ext, filename, file_dir, file_ext)
            else:
                # 优先尝试电视剧解析
                tv_result = self._parse_tv_series_filename(filename_without_ext, filename, file_dir, file_ext)
                if tv_result:
                    return tv_result
                # 电视剧解析失败，尝试电影解析作为备选
                logger.debug("电视剧解析失败，尝试电影解析")
                return self._parse_movie_filename(filename_without_ext, filename, file_dir, file_ext)
            
        except Exception as e:
            logger.error(f"解析视频文件名时发生错误: {e}")
            return None
    
    def _detect_content_type(self, filename):
        """
        通过正则匹配检测内容类型
        
        Args:
            filename: 文件名（不含扩展名）
            
        Returns:
            str: 'movie' 或 'tv_series'
        """
        # 电影特征模式（优先级从高到低）
        movie_patterns = [
            r'.+\s*\(\d{4}\)\s*[-–—]?\s*',  # 包含年份的格式：电影名 (年份)
            r'.+\s+\d{4}\s*[-–—]\s*',      # 电影名 年份 - 格式（更严格）
            r'.+\s+\d{4}\s*$',             # 以年份结尾：电影名 年份
        ]
        
        # 电视剧特征模式（优先级从高到低）
        tv_patterns = [
            r'.*[Ss]\d+[Ee]\d+.*',          # S01E01 格式
            r'.*第\s*\d+\s*[集话期].*',        # 第X集/话/期
            r'.*[Ee][Pp]?\s*\d+.*',         # EP01, E01 格式
            r'.*\s+\d+\s*$',               # 以数字结尾（集数）
            r'.*[-–—]\s*\d+\s*$',          # 以-数字结尾
        ]
        
        # 先检查电影模式
        for pattern in movie_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                logger.debug(f"匹配到电影模式: {pattern}")
                return 'movie'
        
        # 再检查电视剧模式
        for pattern in tv_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                logger.debug(f"匹配到电视剧模式: {pattern}")
                return 'tv_series'
        
        # 默认返回电视剧（保持向后兼容）
        logger.debug("未匹配到明确模式，默认为电视剧")
        return 'tv_series'
    
    def _parse_tv_series_filename(self, filename_without_ext, full_filename, file_dir, file_ext):
        """
        解析电视剧文件名
        """
        # 提取集数信息
        episode_info = self._extract_episode_info(filename_without_ext)
        if episode_info:
            # 提取剧名
            series_name = self._extract_series_name(
                filename_without_ext, episode_info)
            if series_name:
                result = {
                    'series_name': series_name.strip(),
                    'season': episode_info.get('season'),
                    'episode': episode_info['episode'],
                    'original_filename': filename_without_ext,
                    'full_filename': full_filename,
                    'file_dir': file_dir,
                    'file_ext': file_ext,
                    'content_type': 'tv_series'
                }
                logger.info(f"电视剧解析结果: {result}")
                return result
        
        logger.debug(f"无法解析电视剧文件名: {full_filename}")
        return None

    def _parse_movie_filename(self, filename_without_ext, full_filename, file_dir, file_ext):
        """
        解析电影文件名，提取电影名和年份信息
        
        电影文件名格式通常为：电影名 (年份) - 分辨率.扩展名
        例如：红楼梦之金玉良缘 (2024) - 2160p.mkv
        
        Args:
            filename_without_ext: 不包含扩展名的文件名
            full_filename: 包含扩展名的完整文件名
            file_dir: 文件目录
            file_ext: 文件扩展名
            
        Returns:
            dict: 包含电影名、年份等信息的字典，解析失败返回None
        """
        try:
            logger.debug(f"尝试解析电影文件名: {filename_without_ext}")
            
            # 电影文件名的正则表达式模式
            # 匹配格式：电影名 (年份) - 其他信息
            movie_pattern = r'^(.+?)\s*\((\d{4})\)\s*-?\s*(.*?)$'
            
            match = re.match(movie_pattern, filename_without_ext)
            if match:
                movie_name = match.group(1).strip()
                year = int(match.group(2))
                extra_info = match.group(3).strip() if match.group(3) else ''
                
                # 验证年份是否合理（1900-2030）
                if not (1900 <= year <= 2030):
                    logger.debug(f"年份不合理，跳过电影解析: {year}")
                    return None
                
                # 清理电影名中的多余信息
                clean_movie_name = self._clean_movie_name(movie_name)
                if not clean_movie_name or len(clean_movie_name) < 2:
                    logger.debug(f"电影名太短或为空，跳过: {clean_movie_name}")
                    return None
                
                result = {
                    'series_name': clean_movie_name,  # 使用series_name保持兼容性
                    'movie_name': clean_movie_name,   # 电影专用字段
                    'year': year,
                    'season': None,  # 电影没有季数
                    'episode': 1,    # 电影视为第1集
                    'original_filename': filename_without_ext,
                    'full_filename': full_filename,
                    'file_dir': file_dir,
                    'file_ext': file_ext,
                    'content_type': 'movie',
                    'extra_info': extra_info  # 分辨率等额外信息
                }
                
                logger.info(f"电影解析结果: {result}")
                return result
            
            # 如果不匹配标准格式，尝试更宽松的匹配
            # 匹配包含年份的文件名
            loose_pattern = r'^(.+?).*?(\d{4}).*?$'
            loose_match = re.search(loose_pattern, filename_without_ext)
            
            if loose_match:
                movie_name = loose_match.group(1).strip()
                year = int(loose_match.group(2))
                
                # 验证年份是否合理
                if 1900 <= year <= 2030:
                    # 清理电影名
                    clean_movie_name = self._clean_movie_name(movie_name)
                    if clean_movie_name and len(clean_movie_name) >= 2:
                        result = {
                            'series_name': clean_movie_name,
                            'movie_name': clean_movie_name,
                            'year': year,
                            'season': None,
                            'episode': 1,
                            'original_filename': filename_without_ext,
                            'full_filename': full_filename,
                            'file_dir': file_dir,
                            'file_ext': file_ext,
                            'content_type': 'movie',
                            'extra_info': ''
                        }
                        
                        logger.info(f"电影解析结果（宽松匹配）: {result}")
                        return result
            
            logger.debug(f"无法解析为电影文件名: {filename_without_ext}")
            return None
            
        except Exception as e:
            logger.error(f"解析电影文件名时出错: {filename_without_ext}, 错误: {e}")
            return None
    
    def _clean_movie_name(self, movie_name):
        """
        清理电影名称，移除不必要的信息
        
        Args:
            movie_name: 原始电影名
            
        Returns:
            str: 清理后的电影名
        """
        try:
            clean_name = movie_name
            
            # 移除常见的视频质量和编码信息
            quality_patterns = [
                r'\b(1080p|720p|480p|4k|2160p|uhd|hd)\b',
                r'\b(x264|x265|h264|h265|hevc)\b',
                r'\b(bluray|webrip|hdtv|dvdrip|bdrip|web-dl)\b',
                r'\b(aac|ac3|dts|flac|mp3)\b',
                r'\[(.*?)\]',  # 移除方括号内容
            ]
            
            for pattern in quality_patterns:
                clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
            
            # 清理分隔符和多余空格
            clean_name = re.sub(r'[-_\s]+', ' ', clean_name)
            clean_name = clean_name.strip(' -_')
            
            return clean_name
            
        except Exception as e:
            logger.error(f"清理电影名时出错: {movie_name}, 错误: {e}")
            return movie_name

    def _extract_episode_info(self, filename):
        """
        从文件名中提取集数信息

        Returns:
            dict: {'season': 季数, 'episode': 集数} 或 None
        """
        # 尝试各种集数匹配模式
        for i, pattern in enumerate(self.episode_patterns):
            matches = re.finditer(pattern, filename, re.IGNORECASE)

            for match in matches:
                groups = match.groups()

                # S01E14 格式 (有季数和集数)
                if i == 0 and len(groups) == 2:
                    season = int(groups[0])
                    episode = int(groups[1])
                    return {'season': season, 'episode': episode}

                # 其他格式 (只有集数)
                elif len(groups) == 1:
                    episode_num = int(groups[0])

                    # 对于纯数字格式，需要额外验证
                    if i == len(self.episode_patterns) - 1:  # 最后一个模式（纯数字）
                        if self._is_valid_episode_number(episode_num, match, filename):
                            return {'season': None, 'episode': episode_num}
                    else:
                        return {'season': None, 'episode': episode_num}

        return None

    def _is_valid_episode_number(self, episode_num, match, filename):
        """
        验证纯数字是否为有效的集数
        """
        # 集数范围检查 (1-999)
        if not (1 <= episode_num <= 999):
            return False

        # 检查匹配的上下文，避免匹配到分辨率、编码等信息
        match_text = match.group(0)
        start_pos = match.start()
        end_pos = match.end()

        # 获取匹配前后的文本
        before_text = filename[max(0, start_pos-10):start_pos].lower()
        after_text = filename[end_pos:min(len(filename), end_pos+10)].lower()
        context = before_text + match_text + after_text

        # 检查是否包含过滤关键词
        for keyword in self.filter_keywords:
            if keyword in context:
                return False

        # 如果数字前后有特定字符，更可能是集数
        episode_indicators = ['第', '集', 'ep', 'e', '话', '-', '_', ' ']

        for indicator in episode_indicators:
            if indicator in before_text or indicator in after_text:
                return True

        # 如果是两位数且在合理范围内，也认为是集数
        if 10 <= episode_num <= 99:
            return True

        return False

    def _extract_series_name(self, filename, episode_info):
        """
        从文件名中提取剧名
        """
        # 移除集数相关的部分
        clean_name = filename

        # 移除季集信息
        if episode_info.get('season'):
            # 移除 S01E14 格式
            clean_name = re.sub(r'[Ss]\d+[Ee]\d+', '',
                                clean_name, flags=re.IGNORECASE)

        # 移除各种集数格式
        for pattern in self.episode_patterns:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)

        # 移除常见的视频质量和编码信息
        quality_patterns = [
            r'\b(1080p|720p|480p|4k|2160p)\b',
            r'\b(x264|x265|h264|h265)\b',
            r'\b(bluray|webrip|hdtv|dvdrip|bdrip)\b',
            r'\b(aac|ac3|dts|flac|mp3)\b',
            r'\[(.*?)\]',  # 移除方括号内容
            r'\((.*?)\)',  # 移除圆括号内容
        ]

        for pattern in quality_patterns:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)

        # 清理分隔符和多余空格
        clean_name = re.sub(r'[-_\s]+', ' ', clean_name)
        clean_name = clean_name.strip(' -_')

        # 如果剧名为空或太短，尝试更保守的清理
        if not clean_name or len(clean_name) < 2:
            # 重新开始，只移除明确的集数标识
            clean_name = filename
            clean_name = re.sub(r'第\s*\d+\s*集', '', clean_name)
            clean_name = re.sub(r'[Ss]\d+[Ee]\d+', '',
                                clean_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'[Ee][Pp]\s*\d+', '',
                                clean_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'[-_\s]+', ' ', clean_name)
            clean_name = clean_name.strip(' -_')

        return clean_name if clean_name else None

    def generate_danmu_filename(self, video_info, danmu_source='IqiyiID'):
        """
        根据视频信息生成弹幕文件名

        Args:
            video_info: 视频解析信息
            danmu_source: 弹幕源标识

        Returns:
            str: 弹幕文件名 (不包含路径)
        """
        try:
            original_name = video_info['original_filename']

            # 检查原文件名是否已经包含弹幕源后缀，避免重复拼接
            suffix = f"_{danmu_source}"
            if original_name.endswith(suffix):
                danmu_filename = f"{original_name}.xml"
            else:
                danmu_filename = f"{original_name}_{danmu_source}.xml"

            logger.info(f"生成弹幕文件名: {danmu_filename}")
            return danmu_filename

        except Exception as e:
            logger.error(f"生成弹幕文件名时出错: {e}")
            return None

    def get_danmu_filepath(self, video_info, danmu_source='IqiyiID'):
        """
        获取完整的弹幕文件路径

        Args:
            video_info: 视频解析信息
            danmu_source: 弹幕源标识

        Returns:
            str: 完整的弹幕文件路径
        """
        try:
            danmu_filename = self.generate_danmu_filename(
                video_info, danmu_source)
            if not danmu_filename:
                return None

            danmu_filepath = os.path.join(
                video_info['file_dir'], danmu_filename)

            logger.info(f"弹幕文件路径: {danmu_filepath}")
            return danmu_filepath

        except Exception as e:
            logger.error(f"获取弹幕文件路径时出错: {e}")
            return None


# 测试函数
def test_parser():
    """测试视频文件名解析功能"""
    parser = VideoFileParser()

    test_files = [
        "沧元图 - S01E14 - 第 14 集.mp4",
        "沧元图 - S01E48 - 第 48 集.mp4",
        "某剧名 第25集.mkv",
        "动漫名称 EP12.avi",
        "电视剧 12集 1080p.mp4",
        "[字幕组] 剧名 [14].mp4"
    ]

    for filename in test_files:
        print(f"\n测试文件: {filename}")
        result = parser.parse_video_filename(filename)
        if result:
            print(f"  剧名: {result['series_name']}")
            print(f"  季数: {result['season']}")
            print(f"  集数: {result['episode']}")
            danmu_filename = parser.generate_danmu_filename(result)
            print(f"  弹幕文件名: {danmu_filename}")
        else:
            print("  解析失败")


if __name__ == "__main__":
    test_parser()
