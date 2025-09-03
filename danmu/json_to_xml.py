#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
json弹幕转xml工具
用于将json格式的弹幕数据转换为dandanplay标准的xml格式
"""

import json
import logging
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from xml.etree import ElementTree as ET


class JsonToXmlConverter:
    """json弹幕转xml转换器"""
    
    def __init__(self):
        """初始化转换器"""
        self.logger = logging.getLogger(__name__)
        
    def clean_xml_string(self, xml_string: str) -> str:
        """
        移除XML字符串中的无效字符以防止解析错误。
        此函数针对XML 1.0规范中非法的控制字符。
        """
        # XML 1.0 规范允许的字符范围: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
        # 此正则表达式匹配所有不在上述范围内的字符。
        invalid_xml_char_re = re.compile(
            r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]'
        )
        return invalid_xml_char_re.sub('', xml_string)
    
    def xml_escape(self, text: str) -> str:
        """
        转义XML中的特殊字符
        """
        if not text:
            return ''
        
        # 先清理无效字符
        text = self.clean_xml_string(text)
        
        # 转义XML特殊字符
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        
        return text
    
    def generate_xml_from_comments(
        self, 
        comments: List[Dict[str, Any]], 
        episode_id: int = 0,
        provider_name: Optional[str] = "misaka",
        chat_server: Optional[str] = "danmaku.misaka.org"
    ) -> str:
        """
        根据弹幕字典列表生成符合dandanplay标准的XML字符串。
        完全仿照misaka_danmu_server的实现
        """
        root = ET.Element('i')
        ET.SubElement(root, 'chatserver').text = chat_server
        ET.SubElement(root, 'chatid').text = str(episode_id)
        ET.SubElement(root, 'mission').text = '0'
        ET.SubElement(root, 'maxlimit').text = '2000'
        ET.SubElement(root, 'source').text = 'k-v'  # 保持与官方格式一致
        # 新增字段
        ET.SubElement(root, 'sourceprovider').text = provider_name
        ET.SubElement(root, 'datasize').text = str(len(comments))
        
        for comment in comments:
            p_attr = str(comment.get('p', ''))
            d = ET.SubElement(root, 'd', p=p_attr)
            d.text = comment.get('m', '')
            
        return ET.tostring(root, encoding='unicode', xml_declaration=True)
    
    def generate_dandan_xml(self, comments: List[dict]) -> str:
        """
        根据弹幕字典列表生成 dandanplay 格式的 XML 字符串。
        完全仿照misaka_danmu_server的_generate_dandan_xml函数
        """
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<i>',
            '  <chatserver>danmu</chatserver>',
            '  <chatid>0</chatid>',
            '  <mission>0</mission>',
            f'  <maxlimit>{len(comments)}</maxlimit>',
            '  <source>kuyun</source>'
        ]
        
        for comment in comments:
            content = self.xml_escape(comment.get('m', ''))
            p_attr_str = comment.get('p', '0,1,25,16777215')
            p_parts = p_attr_str.split(',')
            
            # 强制修复逻辑：确保 p 属性的格式为 时间,模式,字体大小,颜色,...
            core_parts_end_index = len(p_parts)
            for i, part in enumerate(p_parts):
                if '[' in part and ']' in part:
                    core_parts_end_index = i
                    break
            core_parts = p_parts[:core_parts_end_index]
            optional_parts = p_parts[core_parts_end_index:]

            # 场景1: 缺少字体大小 (e.g., "1.23,1,16777215")
            if len(core_parts) == 3:
                core_parts.insert(2, '25')
            # 场景2: 字体大小为空或无效 (e.g., "1.23,1,,16777215")
            elif len(core_parts) == 4 and (not core_parts[2] or not core_parts[2].strip().isdigit()):
                core_parts[2] = '25'

            final_p_attr = ','.join(core_parts + optional_parts)
            xml_parts.append(f'  <d p="{final_p_attr}">{content}</d>')
            
        xml_parts.append('</i>')
        return '\n'.join(xml_parts)
    
    def convert_json_to_xml(
        self, 
        json_data: Any, 
        output_path: str,
        episode_id: int = 0,
        use_dandan_format: bool = True
    ) -> bool:
        """
        将json弹幕数据转换为xml文件
        
        Args:
            json_data: json弹幕数据，可以是字符串、字典或列表
            output_path: 输出xml文件路径
            episode_id: 分集ID
            use_dandan_format: 是否使用dandan格式（默认True）
            
        Returns:
            转换是否成功
        """
        try:
            # 解析json数据
            if isinstance(json_data, str):
                try:
                    data = json.loads(json_data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON解析失败: {e}")
                    return False
            else:
                data = json_data
            
            # 提取弹幕列表
            comments = []
            
            if isinstance(data, list):
                # 直接是弹幕列表
                comments = data
            elif isinstance(data, dict):
                # 可能包含在某个字段中
                if 'comments' in data:
                    comments = data['comments']
                elif 'data' in data:
                    comments = data['data']
                elif 'danmaku' in data:
                    comments = data['danmaku']
                else:
                    # 尝试直接使用整个字典作为单条弹幕
                    comments = [data]
            
            if not comments:
                self.logger.warning("未找到弹幕数据")
                return False
            
            # 标准化弹幕格式
            normalized_comments = self._normalize_comments(comments)
            
            # 生成XML
            if use_dandan_format:
                xml_content = self.generate_dandan_xml(normalized_comments)
            else:
                xml_content = self.generate_xml_from_comments(normalized_comments, episode_id)
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            self.logger.info(f"成功转换 {len(normalized_comments)} 条弹幕到 {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"转换失败: {e}")
            return False
    
    def _normalize_comments(self, comments: List[Any]) -> List[Dict[str, Any]]:
        """
        标准化弹幕数据格式
        将各种可能的弹幕格式转换为统一的内部格式
        """
        normalized = []
        
        for i, comment in enumerate(comments):
            try:
                if isinstance(comment, dict):
                    # 已经是字典格式
                    normalized_comment = self._normalize_single_comment(comment)
                elif isinstance(comment, (list, tuple)):
                    # 数组格式，尝试解析
                    normalized_comment = self._normalize_array_comment(comment)
                else:
                    # 其他格式，创建默认弹幕
                    normalized_comment = {
                        'p': f'{i * 5},1,25,16777215,0,0,0,{i}',
                        'm': str(comment)
                    }
                
                if normalized_comment:
                    normalized.append(normalized_comment)
                    
            except Exception as e:
                self.logger.warning(f"跳过格式错误的弹幕 {i}: {e}")
                continue
        
        return normalized
    
    def _normalize_single_comment(self, comment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        标准化单条弹幕（字典格式）
        """
        # 提取弹幕文本
        text = ''
        for key in ['m', 'text', 'content', 'message', 'danmaku']:
            if key in comment:
                text = str(comment[key])
                break
        
        if not text:
            return None
        
        # 提取或构造p属性
        if 'p' in comment:
            p_attr = str(comment['p'])
        else:
            # 构造p属性: 时间,模式,字体大小,颜色,时间戳,池,用户ID,弹幕ID
            time_sec = comment.get('time', comment.get('t', 0))
            mode = comment.get('mode', comment.get('type', 1))
            fontsize = comment.get('fontsize', comment.get('size', 25))
            color = comment.get('color', comment.get('c', 16777215))
            timestamp = comment.get('timestamp', comment.get('ts', 0))
            pool = comment.get('pool', 0)
            user_id = comment.get('user_id', comment.get('uid', 0))
            cid = comment.get('cid', comment.get('id', 0))
            
            p_attr = f'{time_sec},{mode},{fontsize},{color},{timestamp},{pool},{user_id},{cid}'
        
        return {
            'p': p_attr,
            'm': text
        }
    
    def _normalize_array_comment(self, comment: List[Any]) -> Optional[Dict[str, Any]]:
        """
        标准化数组格式的弹幕
        通常格式为: [时间, 模式, 字体大小, 颜色, 弹幕文本, ...]
        """
        if len(comment) < 2:
            return None
        
        # 假设最后一个元素是弹幕文本
        text = str(comment[-1])
        
        # 构造p属性
        if len(comment) >= 5:
            # 完整格式
            p_parts = [str(x) for x in comment[:-1]]
            p_attr = ','.join(p_parts)
        else:
            # 简化格式，补充默认值
            time_sec = comment[0] if len(comment) > 0 else 0
            mode = comment[1] if len(comment) > 1 else 1
            fontsize = comment[2] if len(comment) > 2 else 25
            color = comment[3] if len(comment) > 3 else 16777215
            
            p_attr = f'{time_sec},{mode},{fontsize},{color},0,0,0,0'
        
        return {
            'p': p_attr,
            'm': text
        }
    
    def create_test_json_data(self) -> List[Dict[str, Any]]:
        """
        创建测试用的json弹幕数据
        """
        test_comments = [
            {
                'time': 10.5,
                'mode': 1,
                'fontsize': 25,
                'color': 16777215,
                'text': '这是第一条测试弹幕'
            },
            {
                'time': 25.8,
                'mode': 1,
                'fontsize': 25,
                'color': 16711680,
                'text': '这是第二条测试弹幕，红色的'
            },
            {
                'time': 45.2,
                'mode': 4,
                'fontsize': 30,
                'color': 65280,
                'text': '这是底部弹幕，绿色的'
            },
            {
                'time': 60.0,
                'mode': 5,
                'fontsize': 20,
                'color': 255,
                'text': '这是顶部弹幕，蓝色的'
            },
            {
                'time': 120.5,
                'mode': 1,
                'fontsize': 25,
                'color': 16777215,
                'text': '测试中文弹幕：你好世界！'
            }
        ]
        
        return test_comments
    
    def test_conversion(self, output_dir: str = None) -> bool:
        """
        测试转换功能
        
        Args:
            output_dir: 输出目录，默认为test_subtitles
            
        Returns:
            测试是否成功
        """
        if output_dir is None:
            # 默认输出到项目的test_subtitles目录
            current_dir = Path(__file__).parent.parent
            output_dir = current_dir / 'test_subtitles'
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # 生成测试数据
        test_data = self.create_test_json_data()
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f'test_danmu_{timestamp}.xml'
        
        # 执行转换
        success = self.convert_json_to_xml(
            json_data=test_data,
            output_path=str(output_file),
            episode_id=1,
            use_dandan_format=True
        )
        
        if success:
            self.logger.info(f"测试成功！XML文件已保存到: {output_file}")
            print(f"测试成功！XML文件已保存到: {output_file}")
        else:
            self.logger.error("测试失败！")
            print("测试失败！")
        
        return success


def main():
    """主函数，用于测试"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建转换器
    converter = JsonToXmlConverter()
    
    # 执行测试
    print("开始测试json转xml功能...")
    converter.test_conversion()


if __name__ == "__main__":
    main()