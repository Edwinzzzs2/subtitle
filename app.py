from flask import Flask, request, jsonify, send_from_directory
import threading
import os
from datetime import datetime
from watcher import (
    start_watcher, stop_watcher, restart_watcher, is_running, 
    get_processed_files, clear_processed_files, get_config, save_config,
    update_config, get_status, log_message, load_config, setup_logger,
    add_processed_file
)
from subtitle_utils import process_directory, modify_xml, create_test_xml

app = Flask(__name__, static_folder='static', template_folder='static')

# 处理日志
# 统一使用watcher.py的log_message函数记录日志

def process_directory_with_logging(directory):
    """
    处理指定目录下的所有XML文件，并实时记录日志
    返回处理的文件数量
    """
    if not os.path.exists(directory):
        raise Exception(f"目录不存在: {directory}")
    
    count = 0
    total_files = 0
    
    # 先统计总文件数
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.xml'):
                total_files += 1
    
    log_message('info', f"📊 发现 {total_files} 个XML文件待处理")
    
    # 处理文件
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.xml'):
                filepath = os.path.join(root, file)
                try:
                    log_message('info', f"🔄 正在处理: {filepath}")
                    result = modify_xml(filepath)
                    
                    if result is True:
                        count += 1
                        add_processed_file(filepath)  # 添加到处理计数中
                        log_message('info', f"✅ 处理完成: {filepath}")
                    elif result is False:
                        log_message('info', f"⏩ 文件已符合要求: {filepath}")
                    elif result == 'empty':
                        log_message('warning', f"⚠️ 空白文件跳过: {filepath}")
                    elif isinstance(result, tuple) and result[0] == 'error':
                        log_message('error', f"❌ 文件处理失败: {filepath} | {result[1]}")
                    elif result == 'error':
                        log_message('error', f"❌ 文件处理失败: {filepath}")
                except Exception as e:
                    log_message('error', f"❌ 处理文件失败: {filepath}, 错误: {e}")
    
    return count

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/status')
def status():
    watcher_status = get_status()
    return jsonify({
        "running": watcher_status['running'],
        "processed_count": watcher_status['processed_count']
    })

@app.route('/api/start', methods=['POST'])
def start():
    # 直接调用start_watcher，它内部会处理重复启动的情况
    success = start_watcher()
    if success:
        log_message('info', "开始监听字幕文件")
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
                            logs.append({
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'message': line,
                                'level': 'INFO'
                            })
        except Exception as e:
            # 如果读取日志文件失败，添加错误信息
            logs.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
    """立即处理所有监控目录下的文件"""
    try:
        # 获取当前配置的监控目录
        config = get_config()
        watch_dirs = config.get('watch_dirs', [])
        if not watch_dirs and config.get('watch_dir'):
            watch_dirs = [config.get('watch_dir')]
        if not watch_dirs:
            watch_dirs = ['./test_subtitles']  # 默认目录
        
        log_message('info', f"🚀 开始处理所有监控目录: {watch_dirs}")
        
        total_count = 0
        processed_dirs = []
        
        # 处理每个监控目录
        for directory in watch_dirs:
            if os.path.exists(directory):
                log_message('info', f"📁 处理目录: {directory}")
                count = process_directory_with_logging(directory)
                total_count += count
                processed_dirs.append(f"{directory}({count}个文件)")
            else:
                log_message('warning', f"⚠️ 目录不存在，跳过: {directory}")
        
        log_message('info', f"✅ 处理完成，共处理 {total_count} 个文件")
        
        return jsonify({
            "message": f"处理完成，共处理 {total_count} 个文件\n处理的目录: {', '.join(processed_dirs)}", 
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
            valid_keys = ['watch_dir', 'watch_dirs', 'file_extensions', 'wait_time', 'max_retries', 'retry_delay', 'enable_logging', 'log_level', 'max_log_lines', 'keep_log_lines', 'cron_enabled', 'cron_schedule']
            filtered_config = {k: v for k, v in data.items() if k in valid_keys}
            
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

@app.route('/api/create-test', methods=['POST'])
def create_test():
    test_dir = "./test_subtitles"
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, f"test_{datetime.now().strftime('%H%M%S')}.xml")
    create_test_xml(test_file, "text")
    # 文件监听器会自动检测并记录日志，无需手动记录
    return jsonify({"message": f"测试文件已创建: {test_file}", "success": True})

if __name__ == '__main__':
        # 启动时加载一次配置
    load_config()
    setup_logger()
    
    # 启动时自动开始监听
    log_message('info', "程序启动，自动开启文件监听功能")
    start_watcher()
    
    # 禁用重新加载器以避免多进程问题
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)