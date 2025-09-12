#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除监听目录下的ass文件工具
"""

import os
import glob
from pathlib import Path
from .watcher import get_config, log_message


def get_watch_directories():
    """获取监听目录列表
    
    Returns:
        list: 监听目录列表
    """
    config = get_config()
    if config:
        return config.get('watch_dirs', ['./videos', './test_videos'])
    return ['./videos', './test_videos']


def find_ass_files(directories):
    """在指定目录中查找所有ass文件
    
    Args:
        directories (list): 要搜索的目录列表
        
    Returns:
        list: 找到的ass文件路径列表
    """
    ass_files = []

    for directory in directories:
        # 转换为绝对路径
        abs_dir = os.path.abspath(directory)

        if not os.path.exists(abs_dir):
            log_message('warning', f'目录不存在: {abs_dir}')
            continue

        # 使用glob递归搜索所有ass文件
        pattern = os.path.join(abs_dir, '**', '*.ass')
        found_files = glob.glob(pattern, recursive=True)

        ass_files.extend(found_files)
        log_message('info', f'在目录 {abs_dir} 中找到 {len(found_files)} 个ass文件')

    return ass_files


def delete_ass_files():
    """删除监听目录下的所有ass文件
    
    Returns:
        dict: 删除结果统计
    """
    try:
        # 获取监听目录
        watch_dirs = get_watch_directories()
        log_message('info', f'开始扫描监听目录: {watch_dirs}')

        # 查找所有ass文件
        ass_files = find_ass_files(watch_dirs)

        if not ass_files:
            log_message('info', '未找到任何ass文件')
            return {
                'success': True,
                'deleted_count': 0,
                'failed_count': 0,
                'message': '未找到任何ass文件'
            }

        log_message('info', f'找到 {len(ass_files)} 个ass文件，开始删除...')

        deleted_count = 0
        failed_count = 0
        failed_files = []

        # 逐个删除文件
        for file_path in ass_files:
            try:
                os.remove(file_path)
                deleted_count += 1
                log_message('info', f'已删除: {file_path}')
            except Exception as e:
                failed_count += 1
                failed_files.append(file_path)
                log_message('error', f'删除失败 {file_path}: {e}')

        # 返回结果统计
        result = {
            'success': True,
            'deleted_count': deleted_count,
            'failed_count': failed_count,
            'message': f'删除完成: 成功删除 {deleted_count} 个文件'
        }

        if failed_count > 0:
            result['message'] += f', {failed_count} 个文件删除失败'
            result['failed_files'] = failed_files

        log_message('info', result['message'])
        return result

    except Exception as e:
        error_msg = f'删除ass文件时发生错误: {e}'
        log_message('error', error_msg)
        return {
            'success': False,
            'deleted_count': 0,
            'failed_count': 0,
            'message': error_msg
        }


def count_ass_files():
    """统计监听目录下的ass文件数量
    
    Returns:
        dict: 统计结果
    """
    try:
        watch_dirs = get_watch_directories()
        ass_files = find_ass_files(watch_dirs)

        return {
            'success': True,
            'count': len(ass_files),
            'files': ass_files
        }
    except Exception as e:
        log_message('error', f'统计ass文件时发生错误: {e}')
        return {
            'success': False,
            'count': 0,
            'message': str(e)
        }


if __name__ == '__main__':
    # 命令行测试
    print('开始删除ass文件...')
    result = delete_ass_files()
    print(f'删除结果: {result}')
