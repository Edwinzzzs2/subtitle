import os
import asyncio
from pathlib import Path
from datetime import datetime
import pytz

from utils.watcher import log_message, add_processed_file, get_config
from utils.concurrent_processor import get_concurrent_processor


def process_directory_with_logging(directory):
    """
    处理指定目录下的所有视频文件，使用并发处理器下载对应弹幕
    返回处理的文件数量
    """
    if not os.path.exists(directory):
        raise Exception(f"目录不存在: {directory}")

    # 获取支持的视频文件扩展名
    config = get_config()
    file_extensions = config.get(
        'file_extensions', ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'])

    # 收集所有视频文件
    video_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                video_files.append(os.path.join(root, file))

    log_message('info', f"📊 发现 {len(video_files)} 个视频文件待处理")

    if video_files:
        # 使用并发处理器批量处理所有文件
        concurrent_processor = get_concurrent_processor()
        success_count = concurrent_processor.process_files_batch(video_files)
        return success_count
    else:
        log_message('info', "📁 没有找到需要处理的视频文件")
        return 0
