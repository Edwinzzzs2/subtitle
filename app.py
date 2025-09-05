from flask import Flask, request, jsonify, send_from_directory
import threading
import os
import asyncio
import json
from datetime import datetime
from utils import (
    start_watcher, stop_watcher, restart_watcher, is_running,
    get_processed_files, clear_processed_files, get_config, save_config,
    update_config, get_status, log_message, load_config, setup_logger,
    add_processed_file, process_directory_with_logging
)
from version import get_version_info

app = Flask(__name__, static_folder='web/static', template_folder='web/static')

# 处理日志
# 统一使用watcher.py的log_message函数记录日志

# 存储webhook消息的列表，最多保存100条
webhook_messages = []

# process_directory_with_logging 函数已移至 utils/video_processor.py


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/webhook')
def webhook_page():
    return send_from_directory(app.static_folder, 'webhook.html')


@app.route('/api/status')
def status():
    watcher_status = get_status()
    return jsonify({
        "running": watcher_status['running'],
        "processed_count": watcher_status['processed_count'],
        "current_time": watcher_status['current_time']
    })


@app.route('/api/version')
def version():
    """获取版本信息"""
    return jsonify(get_version_info())


@app.route('/api/start', methods=['POST'])
def start():
    # 直接调用start_watcher，它内部会处理重复启动的情况
    success = start_watcher()
    if success:
        log_message('info', "开始监听视频文件")
        return jsonify({"message": "监听器启动成功", "success": True})
    else:
        log_message('error', "监听器启动失败")
        return jsonify({"message": "监听器启动失败", "success": False})


@app.route('/api/stop', methods=['POST'])
def stop():
    if is_running():
        success = stop_watcher()
        if success:
            # log_message('info', "停止监听字幕文件")
            return jsonify({"message": "监听器停止成功", "success": True})
        else:
            log_message('error', "监听器停止失败")
            return jsonify({"message": "监听器停止失败", "success": False})
    return jsonify({"message": "监听器未运行", "success": False})


@app.route('/api/restart', methods=['POST'])
def restart():
    success = restart_watcher()
    if success:
        log_message('info', "重启监听器成功")
        return jsonify({"message": "监听器重启成功", "success": True})
    else:
        log_message('error', "重启监听器失败")
        return jsonify({"message": "监听器重启失败", "success": False})


@app.route('/api/clear-processed', methods=['POST'])
def clear_processed():
    count = clear_processed_files()
    # log_message('info', f"清空已处理文件记录，共 {count} 个文件")
    return jsonify({"message": f"已清空 {count} 个文件的处理记录", "success": True, "count": count})


@app.route('/api/logs')
def get_logs():
    logs = []

    # 统一从watcher.log文件读取所有日志
    log_file_path = os.path.join('logs', 'watcher.log')
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # 获取最后100行，提供更多日志历史
                recent_lines = lines[-100:] if len(lines) > 100 else lines

                for line in recent_lines:
                    line = line.strip()
                    if line:
                        # 解析日志格式: 2025-06-24 23:13:57,077 - subtitle_watcher - INFO - 消息
                        parts = line.split(' - ', 3)
                        if len(parts) >= 4:
                            timestamp = parts[0]
                        # 移除时间戳中的毫秒部分
                        if ',' in timestamp:
                            timestamp = timestamp.split(',')[0]
                            level = parts[2]
                            message = parts[3]
                            logs.append({
                                'timestamp': timestamp,
                                'message': f"[{level}] {message}",
                                'level': level
                            })
                        else:
                            # 如果格式不匹配，直接显示原始行
                            # 使用北京时间
                            from utils.watcher import get_beijing_formatter
                            import pytz
                            beijing_tz = pytz.timezone('Asia/Shanghai')
                            beijing_time = datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')
                            logs.append({
                                'timestamp': beijing_time,
                                'message': line,
                                'level': 'INFO'
                            })
        except Exception as e:
            # 如果读取日志文件失败，添加错误信息
            # 使用北京时间
            import pytz
            beijing_tz = pytz.timezone('Asia/Shanghai')
            beijing_time = datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')
            logs.append({
                'timestamp': beijing_time,
                'message': f"读取日志文件失败: {str(e)}",
                'level': 'ERROR'
            })

    return jsonify({"logs": logs})


@app.route('/api/clear-logs', methods=['POST'])
def clear_logs():
    try:
        # 清空日志文件
        log_file = './logs/watcher.log'
        if os.path.exists(log_file):
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('')  # 清空文件内容

        # 清空已处理文件记录
        cleared_count = clear_processed_files()

        # log_message('info', f"日志已清空，已处理文件记录已重置（清空了 {cleared_count} 个文件记录）")
        return jsonify({"message": "日志已清空", "success": True})
    except Exception as e:
        return jsonify({"message": f"清空日志失败: {str(e)}", "success": False})


@app.route('/api/process-now', methods=['POST'])
def process_now():
    """立即处理所有监控目录下的视频文件，下载对应弹幕"""
    try:
        # 获取当前配置的监控目录
        config = get_config()
        watch_dirs = config.get('watch_dirs', [])
        if not watch_dirs:
            watch_dirs = ['./videos']  # 默认目录

        log_message('info', f"🚀 开始处理所有监控目录下的视频文件: {watch_dirs}")

        total_count = 0
        processed_dirs = []

        # 处理每个监控目录
        for directory in watch_dirs:
            if os.path.exists(directory):
                log_message('info', f"📁 处理目录中的视频文件: {directory}")
                # 使用从 utils/video_processor.py 导入的函数
                count = process_directory_with_logging(directory)
                total_count += count
                processed_dirs.append(f"{directory}({count}个文件)")
            else:
                log_message('warning', f"⚠️ 目录不存在，跳过: {directory}")

        return jsonify({
            "message": f"处理完成，共处理 {total_count} 个视频文件\n处理的目录: {', '.join(processed_dirs)}",
            "success": True,
            "count": total_count,
            "processed_dirs": processed_dirs
        })
    except Exception as e:
        log_message('error', f"❌ 手动处理失败: {str(e)}")
        return jsonify({"message": f"处理失败: {str(e)}", "success": False})


@app.route('/api/reload-config', methods=['POST'])
def reload_config():
    """重新加载配置文件"""
    try:
        load_config()
        log_message('info', "配置文件已重新加载")
        return jsonify({"message": "配置已重新加载", "success": True})
    except Exception as e:
        log_message('error', f"配置重新加载失败: {str(e)}")
        return jsonify({"message": f"配置重新加载失败: {str(e)}", "success": False})


@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({"message": "无效的配置数据", "success": False})

            # 验证配置数据
            valid_keys = ['watch_dirs', 'file_extensions', 'wait_time', 'max_retries', 'retry_delay', 'max_concurrent_workers', 'enable_logging',
                          'log_level', 'max_log_lines', 'keep_log_lines', 'cron_enabled', 'cron_schedule', 'danmu_api']
            filtered_config = {k: v for k,
                               v in data.items() if k in valid_keys}

            if not filtered_config:
                return jsonify({"message": "没有有效的配置项", "success": False})

            # 更新配置
            update_config(filtered_config)

            return jsonify({
                "message": "配置已保存",
                "success": True,
                "updated_keys": list(filtered_config.keys())
            })

        except Exception as e:
            log_message('error', f"配置更新失败: {str(e)}")
            return jsonify({"message": f"配置保存失败: {str(e)}", "success": False})
    else:
        # 返回当前配置
        try:
            current_config = get_config()
            return jsonify({
                "config": current_config,
                "success": True
            })
        except Exception as e:
            return jsonify({"message": f"获取配置失败: {str(e)}", "success": False})


@app.route('/api/danmu-config', methods=['GET', 'POST'])
def danmu_config():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({"message": "无效的弹幕API配置数据", "success": False})

            # 构建弹幕API配置数据
            danmu_api_config = {}
            if 'base_url' in data:
                danmu_api_config['base_url'] = data['base_url']
            if 'token' in data:
                danmu_api_config['token'] = data['token']

            if not danmu_api_config:
                return jsonify({"message": "未提供有效的配置字段", "success": False})

            # 更新弹幕API配置
            danmu_config_data = {'danmu_api': danmu_api_config}
            update_config(danmu_config_data)

            return jsonify({
                "message": "弹幕API配置已保存",
                "success": True
            })

        except Exception as e:
            log_message('error', f"弹幕API配置更新失败: {str(e)}")
            return jsonify({"message": f"弹幕API配置保存失败: {str(e)}", "success": False})
    else:
        # 返回当前弹幕API配置
        try:
            current_config = get_config()
            danmu_api = current_config.get('danmu_api', {})
            return jsonify({
                "danmu_api": danmu_api,
                "success": True
            })
        except Exception as e:
            return jsonify({"message": f"获取弹幕API配置失败: {str(e)}", "success": False})


@app.route('/api/webhook', methods=['POST'])
def receive_webhook():
    """接收webhook消息并存储"""
    try:
        # 获取请求数据
        data = request.get_json(silent=True) or {}
        headers = dict(request.headers)
        
        # 创建webhook消息对象
        webhook_msg = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "headers": headers,
            "data": data,
            "remote_addr": request.remote_addr
        }
        
        # 添加到消息列表，保持最多100条
        global webhook_messages
        webhook_messages.insert(0, webhook_msg)  # 新消息插入到列表开头
        if len(webhook_messages) > 100:
            webhook_messages = webhook_messages[:100]
        
        log_message('info', f"收到webhook消息: {request.remote_addr}")
        
        return jsonify({
            "success": True,
            "message": "Webhook消息已接收"
        })
    except Exception as e:
        log_message('error', f"处理webhook消息失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"处理失败: {str(e)}"
        }), 500


@app.route('/api/webhook/messages', methods=['GET'])
def get_webhook_messages():
    """获取所有webhook消息"""
    return jsonify({
        "success": True,
        "messages": webhook_messages
    })


@app.route('/api/webhook/clear', methods=['POST'])
def clear_webhook_messages():
    """清空所有webhook消息"""
    global webhook_messages
    count = len(webhook_messages)
    webhook_messages = []
    
    log_message('info', f"清空了{count}条webhook消息")
    
    return jsonify({
        "success": True,
        "message": f"已清空{count}条webhook消息"
    })


@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """清除弹幕缓存"""
    try:
        # 尝试获取全局下载器实例
        from utils.watcher import get_global_downloader
        downloader = get_global_downloader()

        # 如果全局实例不存在，创建新的实例
        if downloader is None:
            config = get_config()
            from danmu.danmu_downloader import DanmuDownloader
            downloader = DanmuDownloader(config)
            log_message('debug', "使用新创建的下载器实例清除缓存")
        else:
            log_message('debug', "使用全局下载器实例清除缓存")

        downloader.clear_cache()

        log_message('info', "弹幕缓存已清除")
        return jsonify({
            "success": True,
            "message": "弹幕缓存已清除"
        })

    except Exception as e:
        log_message('error', f"清除缓存失败: {e}")
        return jsonify({
            "success": False,
            "message": f"清除缓存失败: {str(e)}"
        })


@app.route('/api/cache-stats', methods=['GET'])
def get_cache_stats():
    """获取缓存统计信息"""
    try:
        # 尝试获取全局下载器实例
        from utils.watcher import get_global_downloader
        downloader = get_global_downloader()

        # 如果全局实例不存在，创建新的实例
        if downloader is None:
            config = get_config()
            from danmu.danmu_downloader import DanmuDownloader
            downloader = DanmuDownloader(config)
            log_message('debug', "使用新创建的下载器实例获取缓存统计")
        else:
            log_message('debug', "使用全局下载器实例获取缓存统计")

        cache_stats = downloader.get_cache_stats()

        return jsonify({
            "success": True,
            "cache_stats": cache_stats
        })

    except Exception as e:
        log_message('error', f"获取缓存统计失败: {e}")
        return jsonify({
            "success": False,
            "message": f"获取缓存统计失败: {str(e)}"
        })


@app.route('/api/create-test', methods=['POST'])
def create_test():
    test_dir = "./test_videos"
    os.makedirs(test_dir, exist_ok=True)

    # 获取当前测试视频集数
    import glob
    import re

    # 查找现有的测试视频文件
    existing_files = glob.glob(os.path.join(
        test_dir, "凡人修仙传 - S01E* - 第 * 集.mp4"))

    # 确定下一集的集数
    next_episode = 1
    if existing_files:
        # 从文件名中提取集数
        episode_numbers = []
        for file in existing_files:
            match = re.search(r'S01E(\d+)', file)
            if match:
                episode_numbers.append(int(match.group(1)))

        if episode_numbers:
            next_episode = max(episode_numbers) + 1

    # 生成下一个集数的测试文件名
    test_file = os.path.join(
        test_dir, f"凡人修仙传 - S01E{next_episode:02d} - 第 {next_episode} 集.mp4")

    # 创建测试视频文件
    from utils import create_test_video
    create_test_video(test_file, size_kb=2048)  # 创建2MB大小的测试视频文件

    # 文件监听器会自动检测并记录日志，无需手动记录
    return jsonify({"message": f"测试视频文件已创建: {test_file}", "success": True})


if __name__ == '__main__':
    # 启动时加载一次配置
    load_config()
    setup_logger()

    # 配置所有相关模块的日志器
    import logging

    # 获取配置
    config = get_config()
    log_level = getattr(logging, config.get('log_level', 'INFO'))

    # 配置danmu模块的日志器
    danmu_logger = logging.getLogger('danmu.danmu_client')
    danmu_logger.setLevel(log_level)

    # 如果danmu_logger没有处理器，添加与watcher相同的处理器
    if not danmu_logger.handlers:
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 文件处理器
        import os
        os.makedirs('logs', exist_ok=True)
        file_handler = logging.FileHandler(
            'logs/watcher.log', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # 格式化器
        # 使用北京时间格式化器
        from utils.watcher import get_beijing_formatter
        formatter = get_beijing_formatter()
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        danmu_logger.addHandler(console_handler)
        if config.get('enable_logging', True):
            danmu_logger.addHandler(file_handler)

    # 启动时自动开始监听
    log_message('info', "程序启动，自动开启文件监听功能")
    start_watcher()

    # 禁用重新加载器以避免多进程问题
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
