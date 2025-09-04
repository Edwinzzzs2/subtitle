import os
import asyncio
from pathlib import Path

from utils.watcher import log_message, add_processed_file, get_config
from danmu.danmu_downloader import DanmuDownloader


def process_directory_with_logging(directory):
    """
    处理指定目录下的所有视频文件，下载对应弹幕
    返回处理的文件数量
    """
    if not os.path.exists(directory):
        raise Exception(f"目录不存在: {directory}")

    count = 0
    total_files = 0

    # 获取支持的视频文件扩展名
    config = get_config()
    file_extensions = config.get(
        'file_extensions', ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'])

    # 先统计总文件数
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                total_files += 1

    log_message('info', f"📊 发现 {total_files} 个视频文件待处理")

    # 初始化弹幕下载器
    danmu_downloader = DanmuDownloader(config)

    # 处理文件
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                filepath = os.path.join(root, file)
                try:
                    log_message('info', f"🔄 正在处理视频文件: {filepath}")

                    # 异步处理弹幕下载
                    result = asyncio.run(
                        danmu_downloader.process_video_file(filepath))

                    if result and result.get('success'):
                        count += 1
                        add_processed_file(filepath)  # 添加到处理计数中
                        if result.get('skipped'):
                            log_message('info', f"⏩ 弹幕文件已存在: {filepath}")
                        else:
                            # 获取下载的弹幕文件信息
                            downloaded_files = result.get(
                                'downloaded_files', [])
                            if downloaded_files:
                                # 转换为相对路径，与视频路径显示方式保持一致
                                file_paths = [os.path.relpath(
                                    f['file_path'], '.') for f in downloaded_files]
                                provider_info = ', '.join(file_paths)
                            else:
                                provider_info = 'Unknown'
                            series_name = result.get('series_name', '未知')
                            episode = result.get('episode', '未知')
                            log_message(
                                'info', f"✅ 弹幕下载完成: {filepath} -> {provider_info} -> 📊 (弹幕数量: {result.get('danmu_count', 0)} 条")
                    elif result:
                        log_message(
                            'error', f"❌ 弹幕下载失败: {filepath} | {result.get('message', 'Unknown error')}")
                    else:
                        log_message('error', f"❌ 弹幕下载失败: {filepath}")
                except Exception as e:
                    log_message('error', f"❌ 处理视频文件失败: {filepath}, 错误: {e}")

    return count
