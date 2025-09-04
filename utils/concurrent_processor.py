import time
import threading
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

# 避免循环导入，延迟导入watcher模块


@dataclass
class RetryTask:
    """重试任务数据结构"""
    filepath: str
    attempt: int
    max_retries: int
    retry_time: datetime
    last_error: Optional[str] = None


class ConcurrentFileProcessor:
    """并发文件处理器，支持并发重试机制"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.retry_queue = Queue()
        self.processing_files = set()  # 正在处理的文件
        self.retry_thread = None
        self.retry_thread_running = False
        self._danmu_downloader = None
        self._lock = threading.Lock()
        
    def start_retry_processor(self):
        """启动重试处理线程"""
        if self.retry_thread and self.retry_thread.is_alive():
            return
            
        self.retry_thread_running = True
        self.retry_thread = threading.Thread(target=self._retry_processor_loop, daemon=True)
        self.retry_thread.start()
        # 延迟导入避免循环导入
        from .watcher import log_message
        log_message('info', "🔄 并发重试处理器已启动")
        
    def stop_retry_processor(self):
        """停止重试处理线程"""
        self.retry_thread_running = False
        if self.retry_thread and self.retry_thread.is_alive():
            self.retry_thread.join(timeout=5)
        # 延迟导入避免循环导入
        from .watcher import log_message
        log_message('info', "🛑 并发重试处理器已停止")
        
    def shutdown(self):
        """关闭处理器"""
        self.stop_retry_processor()
        self.executor.shutdown(wait=True)
        
    def _get_danmu_downloader(self):
        """获取弹幕下载器实例"""
        if self._danmu_downloader is None:
            # 延迟导入避免循环导入
            from danmu.danmu_downloader import DanmuDownloader
            from .watcher import get_config
            config = get_config()
            self._danmu_downloader = DanmuDownloader(config)
        return self._danmu_downloader
    
    def _process_video_sync(self, filepath):
        """同步处理视频文件"""
        try:
            # 延迟导入避免循环导入
            from .watcher import log_message
            
            downloader = self._get_danmu_downloader()
            # 使用同步版本的方法
            return downloader.process_video_file_sync(filepath)
            
        except Exception as e:
            # 延迟导入避免循环导入
            from .watcher import log_message
            log_message('error', f"同步处理视频文件失败: {filepath}, 错误: {e}")
            return {
                'success': False,
                'message': f'处理失败: {str(e)}',
                'video_file': filepath
            }
        
    def _retry_processor_loop(self):
        """重试处理循环"""
        while self.retry_thread_running:
            try:
                # 收集到期的重试任务
                ready_tasks = []
                current_time = datetime.now()
                
                # 从队列中取出所有到期的任务
                temp_tasks = []
                while True:
                    try:
                        task = self.retry_queue.get_nowait()
                        if task.retry_time <= current_time:
                            ready_tasks.append(task)
                        else:
                            temp_tasks.append(task)
                    except Empty:
                        break
                
                # 将未到期的任务放回队列
                for task in temp_tasks:
                    self.retry_queue.put(task)
                
                # 并发处理到期的重试任务
                if ready_tasks:
                    # 延迟导入避免循环导入
                    from .watcher import log_message
                    log_message('info', f"🔄 开始并发重试 {len(ready_tasks)} 个文件")
                    self._process_retry_tasks_concurrently(ready_tasks)
                
                # 短暂休眠，避免过度占用CPU
                time.sleep(1)
                
            except Exception as e:
                # 延迟导入避免循环导入
                from .watcher import log_message
                log_message('error', f"❌ 重试处理循环出错: {e}")
                time.sleep(5)  # 出错时等待更长时间
                
    def _process_retry_tasks_concurrently(self, tasks: List[RetryTask]):
        """并发处理重试任务"""
        if not tasks:
            return
            
        # 检查线程池是否已关闭
        if self.executor._shutdown:
            # 延迟导入避免循环导入
            from .watcher import log_message
            log_message('warning', f"⚠️ 线程池已关闭，无法处理 {len(tasks)} 个重试任务")
            return
            
        # 提交所有重试任务到线程池
        future_to_task = {}
        for task in tasks:
            try:
                future = self.executor.submit(self._process_single_retry_task, task)
                future_to_task[future] = task
            except RuntimeError as e:
                # 延迟导入避免循环导入
                from .watcher import log_message
                log_message('warning', f"⚠️ 无法提交重试任务: {task.filepath}, 错误: {e}")
            
        # 等待所有任务完成
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                success, result = future.result()
                if not success and task.attempt < task.max_retries:
                    # 重试失败，重新加入重试队列
                    self._schedule_retry(task.filepath, task.attempt + 1, task.max_retries, result.get('message', 'Unknown error'))
            except Exception as e:
                # 延迟导入避免循环导入
                from .watcher import log_message
                log_message('error', f"❌ 重试任务执行异常: {task.filepath}, 错误: {e}")
                
    def _process_single_retry_task(self, task: RetryTask) -> Tuple[bool, Dict[str, Any]]:
        """处理单个重试任务"""
        try:
            # 延迟导入避免循环导入
            from .watcher import log_message
            log_message('debug', f"🔄 重试处理文件 (尝试 {task.attempt}/{task.max_retries}): {task.filepath}")
            
            # 同步处理弹幕下载
            result = self._process_video_sync(task.filepath)
            
            if result and result.get('success'):
                with self._lock:
                    _processed_files.add(task.filepath)
                    
                if result.get('skipped'):
                    log_message('info', f"⏩ 弹幕文件已存在: {task.filepath}")
                else:
                    # 获取下载的弹幕文件信息
                    downloaded_files = result.get('downloaded_files', [])
                    if downloaded_files:
                        import os
                        file_paths = [os.path.relpath(f['file_path'], '.') for f in downloaded_files]
                        provider_info = ', '.join(file_paths)
                    else:
                        provider_info = 'Unknown'
                    
                    log_message('info', f"✅ 重试成功 - 弹幕下载完成: {task.filepath} -> {provider_info} -> 📊 (弹幕数量: {result.get('danmu_count', 0)} 条)")
                    
                    # 更新最后更新时间
                    self._update_last_update_time()
                    
                return True, result
            else:
                error_msg = result.get('message', 'Unknown error') if result else 'No result'
                log_message('error', f"❌ 重试失败: {task.filepath} | {error_msg}")
                return False, result or {'message': error_msg}
                
        except Exception as e:
            log_message('error', f"❌ 重试处理异常: {task.filepath}, 错误: {e}")
            return False, {'message': str(e)}
            
    def _update_last_update_time(self):
        """更新最后更新时间"""
        try:
            from datetime import datetime
            import pytz
            import utils.watcher as watcher_module
            beijing_tz = pytz.timezone('Asia/Shanghai')
            watcher_module._last_update_time = datetime.now(beijing_tz)
        except Exception as e:
            # 延迟导入避免循环导入
            from .watcher import log_message
            log_message('error', f"❌ 更新时间失败: {e}")
            
    def _schedule_retry(self, filepath: str, attempt: int, max_retries: int, error_msg: str = None):
        """安排重试任务"""
        if attempt > max_retries:
            # 延迟导入避免循环导入
            from .watcher import log_message
            log_message('error', f"❌ 文件处理最终失败，已达最大重试次数: {filepath}")
            return
            
        # 延迟导入避免循环导入
        from .watcher import get_config
        config = get_config()
        retry_delay = config.get('retry_delay', 1.0)
        retry_time = datetime.now() + timedelta(seconds=retry_delay)
        
        retry_task = RetryTask(
            filepath=filepath,
            attempt=attempt,
            max_retries=max_retries,
            retry_time=retry_time,
            last_error=error_msg
        )
        
        self.retry_queue.put(retry_task)
        # 延迟导入避免循环导入
        from .watcher import log_message
        log_message('info', f"⏱️ 已安排重试: {filepath} (尝试 {attempt}/{max_retries}，{retry_delay}秒后执行)")
        
    def process_file_concurrent(self, filepath: str) -> bool:
        """并发处理单个文件"""
        if filepath in self.processing_files:
            # 延迟导入避免循环导入
            from .watcher import log_message
            log_message('debug', f"⏭️ 文件正在处理中，跳过: {filepath}")
            return False
            
        # 检查线程池是否已关闭
        if self.executor._shutdown:
            # 延迟导入避免循环导入
            from .watcher import log_message
            log_message('warning', f"⚠️ 线程池已关闭，无法处理文件: {filepath}")
            return False
            
        with self._lock:
            self.processing_files.add(filepath)
            
        try:
            # 延迟导入避免循环导入
            from .watcher import get_config
            config = get_config()
            max_retries = config.get('max_retries', 3)
            
            # 提交到线程池处理
            future = self.executor.submit(self._process_single_file, filepath, max_retries)
            
            # 不等待结果，让它异步执行
            def handle_result(fut):
                try:
                    success, result = fut.result()
                    if not success:
                        # 处理失败，安排重试
                        self._schedule_retry(filepath, 2, max_retries, result.get('message', 'Unknown error'))
                finally:
                    with self._lock:
                        self.processing_files.discard(filepath)
                        
            future.add_done_callback(handle_result)
            return True
            
        except Exception as e:
            with self._lock:
                self.processing_files.discard(filepath)
            # 延迟导入避免循环导入
            from .watcher import log_message
            log_message('error', f"❌ 提交文件处理任务失败: {filepath}, 错误: {e}")
            return False
            
    def _process_single_file(self, filepath: str, max_retries: int) -> Tuple[bool, Dict[str, Any]]:
        """处理单个文件（首次尝试）"""
        try:
            # 延迟导入避免循环导入
            from .watcher import log_message
            log_message('debug', f"🔄 处理视频文件 (尝试 1/{max_retries}): {filepath}")
            
            # 同步处理弹幕下载
            result = self._process_video_sync(filepath)
            
            if result and result.get('success'):
                # 延迟导入避免循环导入
                from .watcher import _processed_files
                # 延迟导入避免循环导入
                from .watcher import _processed_files
                with self._lock:
                    _processed_files.add(filepath)
                    
                if result.get('skipped'):
                    log_message('info', f"⏩ 弹幕文件已存在: {filepath}")
                else:
                    # 获取下载的弹幕文件信息
                    downloaded_files = result.get('downloaded_files', [])
                    if downloaded_files:
                        import os
                        file_paths = [os.path.relpath(f['file_path'], '.') for f in downloaded_files]
                        provider_info = ', '.join(file_paths)
                    else:
                        provider_info = 'Unknown'
                    
                    log_message('info', f"✅ 弹幕下载完成: {filepath} -> {provider_info} -> 📊 (弹幕数量: {result.get('danmu_count', 0)} 条)")
                    
                    # 更新最后更新时间
                    self._update_last_update_time()
                    
                return True, result
            else:
                error_msg = result.get('message', 'Unknown error') if result else 'No result'
                log_message('error', f"❌ 弹幕下载失败: {filepath} | {error_msg}")
                return False, result or {'message': error_msg}
                
        except Exception as e:
            log_message('error', f"❌ 处理视频文件时出错: {filepath}, 错误: {e}")
            return False, {'message': str(e)}
            
    def process_files_batch(self, filepaths: List[str]) -> int:
        """批量并发处理文件"""
        if not filepaths:
            return 0
            
        # 延迟导入避免循环导入
        from .watcher import log_message
        log_message('info', f"🚀 开始并发处理 {len(filepaths)} 个文件")
        
        success_count = 0
        # 延迟导入避免循环导入
        from .watcher import get_config
        config = get_config()
        max_retries = config.get('max_retries', 3)
        
        # 提交所有文件到线程池
        future_to_filepath = {}
        for filepath in filepaths:
            if filepath not in self.processing_files:
                with self._lock:
                    self.processing_files.add(filepath)
                future = self.executor.submit(self._process_single_file, filepath, max_retries)
                future_to_filepath[future] = filepath
        
        # 等待所有任务完成
        for future in as_completed(future_to_filepath):
            filepath = future_to_filepath[future]
            try:
                success, result = future.result()
                if success:
                    success_count += 1
                else:
                    # 处理失败，安排重试
                    self._schedule_retry(filepath, 2, max_retries, result.get('message', 'Unknown error'))
            except Exception as e:
                # 延迟导入避免循环导入
                from .watcher import log_message
                log_message('error', f"❌ 批量处理任务执行异常: {filepath}, 错误: {e}")
            finally:
                with self._lock:
                    self.processing_files.discard(filepath)
                    
        log_message('info', f"✅ 批量处理完成，成功 {success_count}/{len(filepaths)} 个文件")
        return success_count
        
    def get_status(self) -> Dict[str, Any]:
        """获取处理器状态"""
        return {
            'processing_count': len(self.processing_files),
            'retry_queue_size': self.retry_queue.qsize(),
            'retry_processor_running': self.retry_thread_running,
            'max_workers': self.max_workers
        }


# 全局并发处理器实例
_concurrent_processor: Optional[ConcurrentFileProcessor] = None


def get_concurrent_processor() -> ConcurrentFileProcessor:
    """获取全局并发处理器实例"""
    global _concurrent_processor
    # 延迟导入避免循环导入
    from .watcher import get_config
    config = get_config()
    max_workers = config.get('max_concurrent_workers', 4)  # 可配置的并发数
    
    # 如果处理器不存在，创建新的
    if _concurrent_processor is None:
        _concurrent_processor = ConcurrentFileProcessor(max_workers=max_workers)
        _concurrent_processor.start_retry_processor()
        # 延迟导入避免循环导入
        from .watcher import log_message
        log_message('info', f"🚀 并发处理器已启动，工作线程数: {max_workers}")
    # 如果并发数配置发生变化，重新创建
    elif _concurrent_processor.max_workers != max_workers:
        # 延迟导入避免循环导入
        from .watcher import log_message
        log_message('info', f"🔄 并发数配置变更 ({_concurrent_processor.max_workers} -> {max_workers})，重新初始化处理器")
        old_processor = _concurrent_processor
        # 先创建新的处理器
        _concurrent_processor = ConcurrentFileProcessor(max_workers=max_workers)
        _concurrent_processor.start_retry_processor()
        # 再关闭旧的处理器
        old_processor.shutdown()
        log_message('info', f"🚀 并发处理器已重新启动，工作线程数: {max_workers}")
    
    return _concurrent_processor


def shutdown_concurrent_processor():
    """关闭全局并发处理器"""
    global _concurrent_processor
    if _concurrent_processor:
        _concurrent_processor.shutdown()
        _concurrent_processor = None