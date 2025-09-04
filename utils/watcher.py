import time
import threading
import os
import json
import logging
import time
import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .subtitle_utils import modify_xml
# 延迟导入避免循环导入
# from danmu.danmu_downloader import DanmuDownloader

# 配置文件路径
CONFIG_FILE = "./config/config.json"

# 默认配置
DEFAULT_CONFIG = {
    "watch_dirs": ["./videos"],
    "file_extensions": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    "wait_time": 0.5,
    "max_retries": 3,
    "retry_delay": 1.0,
    "enable_logging": True,
    "log_level": "INFO",
    "cron_schedule": "0 5 * * *",
    "cron_enabled": False
}

# 全局变量
_running = False
_observer = None
_processed_files = set()  # 只记录真正处理过的文件
_config = None
_logger = None
_log_check_counter = 0  # 日志检查计数器
_handler = None  # 全局处理器实例
_danmu_downloader = None  # 弹幕下载器实例

def load_config():
    """加载配置文件"""
    global _config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                _config = {**DEFAULT_CONFIG, **json.load(f)}
        else:
            _config = DEFAULT_CONFIG.copy()
            save_config()
        # 重新设置日志器以应用新的日志配置
        setup_logger()
    except Exception as e:
        print(f"⚠️ 配置文件加载失败，使用默认配置: {e}")
        _config = DEFAULT_CONFIG.copy()
        setup_logger()

def save_config():
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(_config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_message('error', f"配置文件保存失败: {e}")
        print(f"⚠️ 配置文件保存失败: {e}")

def setup_logger():
    """设置日志器"""
    global _logger
    if not _config.get('enable_logging', True):
        _logger = None
        return
    
    _logger = logging.getLogger('subtitle_watcher')
    _logger.setLevel(getattr(logging, _config.get('log_level', 'INFO')))
    
    # 清除现有的处理器
    _logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 文件处理器
    os.makedirs('logs', exist_ok=True)
    file_handler = logging.FileHandler('logs/watcher.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    _logger.addHandler(console_handler)
    if _config.get('enable_logging', True):
        _logger.addHandler(file_handler)
    
    # 启动时检查日志文件大小
    check_and_truncate_log()

def check_and_truncate_log():
    """检查日志文件行数，超过配置的最大行数则自动清空"""
    if _config is None:
        return
        
    log_file_path = 'logs/watcher.log'
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                line_count = len(lines)
            
            max_lines = _config.get('max_log_lines', 3000)
            keep_lines = _config.get('keep_log_lines', 1000)
            
            if line_count > max_lines:
                # 保留最后指定行数，删除前面的
                with open(log_file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-keep_lines:])
                print(f"📝 日志文件已自动清理，从 {line_count} 行减少到 {keep_lines} 行")
                if _logger:
                    _logger.info(f"日志文件已自动清理，从 {line_count} 行减少到 {keep_lines} 行")
        except Exception as e:
            print(f"📝 检查日志文件时出错: {e}")
            if _logger:
                _logger.error(f"检查日志文件时出错: {e}")

def log_message(level, message):
    """统一的日志记录函数"""
    global _log_check_counter
    
    if _logger:
        getattr(_logger, level.lower())(message)
    print(f"📝 {message}")
    
    # 每100次日志写入后检查一次文件大小，避免频繁IO操作
    _log_check_counter += 1
    if _log_check_counter >= 100:
        check_and_truncate_log()
        _log_check_counter = 0

class SubtitleHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.processing_files = set()  # 记录正在处理的文件，避免重复处理
        self.recent_events = {}  # 记录最近的事件时间，用于去重
    
    def on_created(self, event):
        if not event.is_directory and self._is_valid_file(event.src_path):
            if event.src_path not in self.processing_files:
                # 检查是否在短时间内有相同文件的事件，避免重复处理
                if self._should_process_event(event.src_path, 'created'):
                    self.processing_files.add(event.src_path)
                    log_message('info', f"📄 检测到新文件（创建）: {event.src_path}")
                    # 等待文件写入完成
                    time.sleep(_config.get('wait_time', 0.5))
                    self.process_file(event.src_path)
                    self.processing_files.discard(event.src_path)
    
    # 已移除on_modified方法，因为我们只关注视频文件的创建和移动事件
    
    def on_moved(self, event):
        if not event.is_directory and self._is_valid_file(event.dest_path):
            if event.dest_path not in self.processing_files:
                # 检查是否在短时间内有相同文件的事件，避免重复处理
                if self._should_process_event(event.dest_path, 'moved'):
                    self.processing_files.add(event.dest_path)
                    log_message('info', f"📦 检测到新文件（移动/复制）: {event.dest_path}")
                    # 等待文件写入完成
                    time.sleep(_config.get('wait_time', 0.5))
                    self.process_file(event.dest_path)
                    self.processing_files.discard(event.dest_path)
    
    def _should_process_event(self, filepath, event_type):
        """检查是否应该处理此事件，避免短时间内重复处理同一文件"""
        current_time = time.time()
        event_key = f"{filepath}_{event_type}"
        
        # 清理过期的事件记录（超过5秒的记录）
        expired_keys = [key for key, timestamp in self.recent_events.items() 
                       if current_time - timestamp > 5.0]
        for key in expired_keys:
            del self.recent_events[key]
        
        # 精确去重：只检查完全匹配的事件键
        if event_key in self.recent_events:
            last_time = self.recent_events[event_key]
            # 根据事件类型设置不同的去重时间
            if event_type == 'created':
                dedup_time = 0.8  # created事件使用较短的去重时间
            else:
                dedup_time = 2.0  # 其他事件使用默认去重时间
                
            if current_time - last_time < dedup_time:
                return False  # 短时间内有相同的事件，跳过处理
        
        # 记录当前事件
        self.recent_events[event_key] = current_time
        return True
    
    def _is_valid_file(self, filepath):
        """检查文件是否为有效的视频文件"""
        # 检查文件扩展名
        file_ext = os.path.splitext(filepath)[1].lower()
        video_extensions = _config.get('file_extensions', [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"])
        
        if file_ext not in video_extensions:
            return False
        
        # 检查文件是否存在且可读
        try:
            if not os.path.isfile(filepath) or not os.access(filepath, os.R_OK):
                return False
            
            # 等待一小段时间，防止文件正在写入中
            time.sleep(0.1)
                
            return True
        except Exception as e:
            # 只有当文件不在处理列表中时才记录错误，避免重复日志
            if filepath not in self.processing_files:
                log_message('error', f"❌ 文件验证失败: {filepath}, 错误: {e}")
            return False
    
    def process_file(self, filepath):
        """处理视频文件，自动下载对应弹幕"""
        
        max_retries = _config.get('max_retries', 3)
        retry_delay = _config.get('retry_delay', 1.0)
        
        for attempt in range(max_retries):
            try:
                log_message('debug', f"🔄 处理视频文件 (尝试 {attempt+1}/{max_retries}): {filepath}")
                
                # 初始化弹幕下载器
                global _danmu_downloader
                if _danmu_downloader is None:
                    # 延迟导入避免循环导入
                    from danmu.danmu_downloader import DanmuDownloader
                    _danmu_downloader = DanmuDownloader(_config)
                
                # 异步处理弹幕下载
                result = asyncio.run(self._process_video_async(filepath))
                
                if result and result.get('success'):
                    _processed_files.add(filepath)
                    if result.get('skipped'):
                        log_message('info', f"⏩ 弹幕文件已存在: {filepath}")
                    else:
                        # 获取下载的弹幕文件信息
                        downloaded_files = result.get('downloaded_files', [])
                        if downloaded_files:
                            # 转换为相对路径，与视频路径显示方式保持一致
                            file_paths = [os.path.relpath(f['file_path'], '.') for f in downloaded_files]
                            provider_info = ', '.join(file_paths)
                        else:
                            provider_info = 'Unknown'
                        series_name = result.get('series_name', '未知')
                        episode = result.get('episode', '未知')
                        log_message('info', f"✅ 弹幕下载完成: {filepath} -> {provider_info} -> 📊 (弹幕数量: {result.get('danmu_count', 0)} 条")
                elif result:
                    log_message('error', f"❌ 弹幕下载失败: {filepath} | {result.get('message', 'Unknown error')}")
                    # 处理失败的情况，继续重试机制
                    continue
                else:
                    log_message('error', f"❌ 弹幕下载失败: {filepath}")
                    # 处理失败的情况，继续重试机制
                    continue
                
                # 处理成功，跳出重试循环
                break
                
            except Exception as e:
                log_message('error', f"❌ 处理视频文件时出错 (尝试 {attempt+1}/{max_retries}): {filepath}, 错误: {e}")
                
                # 如果不是最后一次尝试，则等待后重试
                if attempt < max_retries - 1:
                    log_message('info', f"⏱️ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
    
    async def _process_video_async(self, filepath):
        """异步处理视频文件弹幕下载"""
        global _danmu_downloader
        try:
            return await _danmu_downloader.process_video_file(filepath)
        except Exception as e:
            log_message('error', f"❌ 异步处理视频文件失败: {filepath}, 错误: {e}")
            return None

def start_watcher():
    """启动文件监听器"""
    global _running, _observer, _config, _handler
    
    # 初始化配置和日志
    if _config is None:
        load_config()
        setup_logger()
    
    # 如果已经在运行，先停止现有的监听器
    if _running:
        log_message('info', "🔄 停止现有监听器")
        stop_watcher()
        time.sleep(0.5)  # 等待完全停止
    
    try:
        # 支持多个监听目录
        watch_dirs = _config.get('watch_dirs', [])
        if not watch_dirs:
            watch_dirs = ['./videos']
        
        if not watch_dirs:
            raise ValueError("没有配置监听目录")
        
        _running = True
        _observer = Observer()
        
        # 创建或重置全局处理器实例
        if _handler is None:
            _handler = SubtitleHandler()
        else:
            # 重置处理器状态
            _handler.processing_files.clear()
        
        # 为每个目录设置监听
        valid_dirs = []
        for watch_dir in watch_dirs:
            try:
                # 确保监听目录存在
                os.makedirs(watch_dir, exist_ok=True)
                
                # 验证目录权限
                if not os.access(watch_dir, os.R_OK | os.W_OK):
                    log_message('warning', f"⚠️ 跳过无权限目录: {watch_dir}")
                    continue
                
                _observer.schedule(_handler, watch_dir, recursive=True)
                valid_dirs.append(os.path.abspath(watch_dir))
                log_message('info', f"📁 已添加监听目录: {os.path.abspath(watch_dir)}")
                
            except Exception as e:
                log_message('warning', f"⚠️ 跳过无效目录 {watch_dir}: {e}")
                continue
        
        if not valid_dirs:
            raise ValueError("没有有效的监听目录")
        
        _observer.start()
        
        log_message('info', f"👀 开始监听 {len(valid_dirs)} 个目录")
        for dir_path in valid_dirs:
            log_message('info', f"  - {dir_path}")
        log_message('info', f"🔍 监听器状态: 运行中")
        log_message('info', f"📋 支持的视频文件类型: {_config.get('file_extensions', ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'])}")
        
        return True
        
    except Exception as e:
        _running = False
        log_message('error', f"❌ 启动监听器失败: {e}")
        return False

def stop_watcher():
    """停止文件监听器"""
    global _running, _observer, _handler
    
    if not _running:
        log_message('warning', "⚠️ 监听器未运行")
        return False
    
    try:
        _running = False
        if _observer:
            _observer.stop()
            _observer.join(timeout=5)  # 设置超时避免无限等待
            _observer = None
        
        # 清理处理器状态
        if _handler:
            _handler.processing_files.clear()
        
        log_message('info', "🛑 停止监听")
        return True
        
    except Exception as e:
        log_message('error', f"❌ 停止监听器失败: {e}")
        return False

def restart_watcher():
    """重启文件监听器"""
    log_message('info', "🔄 重启监听器...")
    stop_watcher()
    time.sleep(1)  # 等待完全停止
    return start_watcher()

def is_running():
    """检查监听器是否运行中"""
    return _running and _observer is not None and _observer.is_alive()

def get_processed_files():
    """获取已处理文件列表"""
    return list(_processed_files)

def clear_processed_files():
    """清空已处理文件记录"""
    global _processed_files
    count = len(_processed_files)
    _processed_files.clear()
    log_message('info', f"🗑️ 已清空 {count} 个文件的处理记录")
    return count

def add_processed_file(filepath):
    """手动添加已处理文件到计数中"""
    global _processed_files
    _processed_files.add(filepath)
    log_message('debug', f"📝 已添加到处理记录: {filepath}")

def get_config():
    """获取当前配置"""
    if _config is None:
        load_config()
    return _config.copy()

def update_config(new_config):
    """更新配置"""
    global _config
    if _config is None:
        load_config()
    
    _config.update(new_config)
    save_config()
    
    # 如果日志相关配置发生变化，重新设置日志器
    if any(key in new_config for key in ['enable_logging', 'log_level']):
        setup_logger()
    
    
    # 如果监听器正在运行，提示重启
    if _running:
        log_message('info', "💡 配置已更新，建议重启监听器以应用新配置")
    else:
        log_message('info', "⚙️ 配置已更新")

def get_status():
    """获取监听器详细状态"""
    return {
        'running': is_running(),
        'processed_count': len(_processed_files)
    }

# 初始化配置（模块加载时）
load_config()
setup_logger()