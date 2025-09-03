#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目公共配置文件
统一管理弹幕源配置等公共变量
"""

# 弹幕源配置
DANMU_SOURCES = {
    'iqiyi': 'IqiyiID',
    'bilibili': 'BilibiliID', 
    'tencent': 'TencentID',
    'youku': 'YoukuID'
}

# 默认弹幕源
DEFAULT_SOURCE = 'iqiyi'

# 支持的视频文件扩展名
SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']

# 支持的字幕文件扩展名
SUPPORTED_SUBTITLE_EXTENSIONS = ['.xml', '.srt', '.ass', '.vtt']