from flask import Flask, request, jsonify, send_from_directory
import threading
import os
import asyncio
from datetime import datetime
from utils import (
    start_watcher, stop_watcher, restart_watcher, is_running, 
    get_processed_files, clear_processed_files, get_config, save_config,
    update_config, get_status, log_message, load_config, setup_logger,
    add_processed_file, modify_xml, create_test_xml
)
from version import get_version_info

app = Flask(__name__, static_folder='web/static', template_folder='web/static')

# 处理日志
# 统一使用watcher.py的log_message函数记录日志

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
    file_extensions = config.get('file_extensions', ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'])
    
    # 先统计总文件数
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                total_files += 1
    
    log_message('info', f"📊 发现 {total_files} 个视频文件待处理")
    
    # 初始化弹幕下载器
    from danmu.danmu_downloader import DanmuDownloader
    danmu_downloader = DanmuDownloader(config)
    
    # 处理文件
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                filepath = os.path.join(root, file)
                try:
                    log_message('info', f"🔄 正在处理视频文件: {filepath}")
                    
                    # 异步处理弹幕下载
                    result = asyncio.run(danmu_downloader.process_video_file(filepath))
                    
                    if result and result.get('success'):
                        count += 1
                        add_processed_file(filepath)  # 添加到处理计数中
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
                    else:
                        log_message('error', f"❌ 弹幕下载失败: {filepath}")
                except Exception as e:
                    log_message('error', f"❌ 处理视频文件失败: {filepath}, 错误: {e}")
    
    return count

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/status')
def status():
    watcher_status = get_status()
    return jsonify({
        "running": watcher_status['running'],
        "processed_count": watcher_status['processed_count']
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
                count = process_directory_with_logging(directory)
                total_count += count
                processed_dirs.append(f"{directory}({count}个文件)")
            else:
                log_message('warning', f"⚠️ 目录不存在，跳过: {directory}")
        
        log_message('info', f"✅ 处理完成，共处理 {total_count} 个视频文件")
        
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
            valid_keys = ['watch_dirs', 'file_extensions', 'wait_time', 'max_retries', 'retry_delay', 'enable_logging', 'log_level', 'max_log_lines', 'keep_log_lines', 'cron_enabled', 'cron_schedule', 'danmu_api']
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

@app.route('/api/test-danmu', methods=['POST'])
def test_danmu():
    """测试弹幕功能（新版API）"""
    try:
        from danmu import DanmuClient
        from danmu.json_to_xml import JsonToXmlConverter
        import os
        from datetime import datetime
        
        # 创建弹幕客户端实例
        danmu_client = DanmuClient()
        
        # 创建json转xml转换器
        converter = JsonToXmlConverter()
        
        # 使用新版API获取作品列表
        library_result = danmu_client.get_library_list()
        if not library_result or not library_result.get('success'):
            return jsonify({
                'success': False,
                'message': f'获取作品列表失败: {library_result.get("errorMessage", "未知错误")}'
            })
        
        # 搜索匹配的动漫
        animes = library_result.get('animes', [])
        keyword = '凡人修仙传'
        matched_anime = None
        for anime in animes:
            if keyword in anime.get('title', ''):
                matched_anime = anime
                break
        
        if not matched_anime:
            return jsonify({
                'success': False,
                'message': f'未找到匹配的动漫: {keyword}',
                'total_animes': len(animes)
            })
        
        # 使用新版API获取弹幕数据
        danmaku_data = danmu_client.get_danmaku_by_title_and_episode(
            title=matched_anime.get('title'),
            season=matched_anime.get('season', 1),
            episode_index=1
        )
        
        xml_file_path = None
        danmu_count = 0
        
        if danmaku_data:
            danmu_count = danmaku_data.get('count', 0)
            comments_data = danmaku_data.get('comments', [])
            
            # 转换为XML文件
            if comments_data:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                xml_filename = f'test_danmu_{timestamp}.xml'
                xml_file_path = os.path.join('videos', xml_filename)
                
                # 确保videos目录存在
                os.makedirs('videos', exist_ok=True)
                
                # 执行转换
                conversion_success = converter.convert_json_to_xml(
                    json_data=comments_data,
                    output_path=xml_file_path,
                    episode_id=f"{matched_anime.get('title')}_S{matched_anime.get('season', 1)}E1",
                    use_dandan_format=True,
                    provider_name="dandanplay"
                )
                
                if not conversion_success:
                    xml_file_path = None
        
        # 如果没有获取到真实弹幕数据，则使用测试数据
        if danmu_count == 0:
            # 使用测试数据
            test_success = converter.test_conversion('videos')
            if test_success:
                # 查找刚创建的测试文件
                test_files = [f for f in os.listdir('videos') if f.startswith('test_danmu_') and f.endswith('.xml')]
                if test_files:
                    xml_file_path = os.path.join('videos', sorted(test_files)[-1])  # 获取最新的文件
                    danmu_count = 5  # 测试数据有5条弹幕
        
        return jsonify({
            'success': True,
            'matched_anime': matched_anime.get('title', '未知') if matched_anime else None,
            'danmu_count': danmu_count,
            'xml_file': xml_file_path if xml_file_path else None,
            'xml_created': xml_file_path is not None
        })
        
    except Exception as e:
        import traceback
        error_msg = f'弹幕测试失败: {str(e)}'
        print(f"Error in test_danmu: {error_msg}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.route('/api/create-test', methods=['POST'])
def create_test():
    test_dir = "./test_videos"
    os.makedirs(test_dir, exist_ok=True)
    
    # 获取当前测试视频集数
    import glob
    import re
    
    # 查找现有的测试视频文件
    existing_files = glob.glob(os.path.join(test_dir, "凡人修仙传 - S01E* - 第 * 集.mp4"))
    
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
    
    # 创建测试视频文件名
    test_file = os.path.join(test_dir, f"凡人修仙传 - S01E{next_episode} - 第 {next_episode} 集.mp4")
    
    # 创建测试视频文件
    from utils import create_test_video
    create_test_video(test_file, size_kb=2048)  # 创建2MB大小的测试视频文件
    
    # 文件监听器会自动检测并记录日志，无需手动记录
    return jsonify({"message": f"测试视频文件已创建: {test_file}", "success": True})

if __name__ == '__main__':
        # 启动时加载一次配置
    load_config()
    setup_logger()
    
    # 启动时自动开始监听
    log_message('info', "程序启动，自动开启文件监听功能")
    start_watcher()
    
    # 禁用重新加载器以避免多进程问题
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)