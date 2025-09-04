#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
弹幕缓存机制测试脚本

测试DanmuClient的缓存功能是否正常工作
"""

import time
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接导入DanmuClient，避免通过__init__.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'danmu'))
from danmu_client import DanmuClient

def test_danmu_client_cache():
    """测试DanmuClient的缓存功能"""
    print("\n=== 测试DanmuClient缓存功能 ===")
    
    client = DanmuClient()
    
    # 测试作品列表缓存
    print("\n1. 测试作品列表缓存")
    start_time = time.time()
    result1 = client.get_library_list(use_cache=True)
    time1 = time.time() - start_time
    print(f"第一次请求耗时: {time1:.2f}秒, 来自缓存: {result1.get('from_cache', False)}")
    
    start_time = time.time()
    result2 = client.get_library_list(use_cache=True)
    time2 = time.time() - start_time
    print(f"第二次请求耗时: {time2:.2f}秒, 来自缓存: {result2.get('from_cache', False)}")
    
    if result2.get('from_cache'):
        print("✓ 作品列表缓存工作正常")
    else:
        print("✗ 作品列表缓存未生效")
    
    # 获取缓存统计信息
    cache_stats = client.get_cache_stats()
    print(f"\n缓存统计信息: {cache_stats}")
    
    # 测试弹幕源缓存（如果有作品数据）
    if result1.get('success') and result1.get('animes'):
        animes = result1.get('animes', [])
        if animes:
            anime = animes[0]  # 取第一个作品
            anime_id = anime.get('animeId')
            
            print(f"\n2. 测试弹幕源缓存 (作品ID: {anime_id})")
            start_time = time.time()
            sources1 = client.get_anime_sources(anime_id, use_cache=True)
            time1 = time.time() - start_time
            print(f"第一次请求耗时: {time1:.2f}秒, 来自缓存: {sources1.get('from_cache', False)}")
            
            start_time = time.time()
            sources2 = client.get_anime_sources(anime_id, use_cache=True)
            time2 = time.time() - start_time
            print(f"第二次请求耗时: {time2:.2f}秒, 来自缓存: {sources2.get('from_cache', False)}")
            
            if sources2.get('from_cache'):
                print("✓ 弹幕源缓存工作正常")
            else:
                print("✗ 弹幕源缓存未生效")
            
            # 测试分集列表缓存（如果有弹幕源数据）
            if sources1.get('success') and sources1.get('sources'):
                sources = sources1.get('sources', [])
                if sources:
                    source = sources[0]  # 取第一个弹幕源
                    source_id = source.get('sourceId')
                    
                    print(f"\n3. 测试分集列表缓存 (源ID: {source_id})")
                    start_time = time.time()
                    episodes1 = client.get_source_episodes(source_id, use_cache=True)
                    time1 = time.time() - start_time
                    print(f"第一次请求耗时: {time1:.2f}秒, 来自缓存: {episodes1.get('from_cache', False)}")
                    
                    start_time = time.time()
                    episodes2 = client.get_source_episodes(source_id, use_cache=True)
                    time2 = time.time() - start_time
                    print(f"第二次请求耗时: {time2:.2f}秒, 来自缓存: {episodes2.get('from_cache', False)}")
                    
                    if episodes2.get('from_cache'):
                        print("✓ 分集列表缓存工作正常")
                    else:
                        print("✗ 分集列表缓存未生效")
    
    # 最终缓存统计
    final_stats = client.get_cache_stats()
    print(f"\n最终缓存统计: {final_stats}")

def test_cache_performance():
    """测试缓存性能提升"""
    print("\n=== 测试缓存性能提升 ===")
    
    client = DanmuClient()
    
    # 清空缓存确保测试准确性
    client.clear_cache()
    
    print("\n测试多次请求同一作品的弹幕源（模拟处理同一视频不同集数的场景）")
    
    # 先获取作品列表
    library_result = client.get_library_list(use_cache=True)
    if not library_result.get('success') or not library_result.get('animes'):
        print("无法获取作品列表，跳过性能测试")
        return
    
    anime = library_result.get('animes', [])[0]
    anime_id = anime.get('animeId')
    anime_title = anime.get('title', 'Unknown')
    
    print(f"\n使用作品: {anime_title} (ID: {anime_id})")
    
    # 模拟处理同一视频的多个集数（多次请求弹幕源）
    times = []
    for i in range(5):
        start_time = time.time()
        result = client.get_anime_sources(anime_id, use_cache=True)
        elapsed = time.time() - start_time
        times.append(elapsed)
        
        from_cache = result.get('from_cache', False)
        cache_status = "缓存" if from_cache else "API"
        print(f"第{i+1}次请求: {elapsed:.3f}秒 ({cache_status})")
    
    # 分析性能提升
    first_request = times[0]
    cached_requests = times[1:]
    avg_cached_time = sum(cached_requests) / len(cached_requests)
    
    improvement = (first_request - avg_cached_time) / first_request * 100
    print(f"\n性能分析:")
    print(f"首次请求(API): {first_request:.3f}秒")
    print(f"缓存请求平均: {avg_cached_time:.3f}秒")
    print(f"性能提升: {improvement:.1f}%")
    
    if improvement > 50:
        print("✓ 缓存显著提升了性能")
    elif improvement > 20:
        print("✓ 缓存有效提升了性能")
    else:
        print("? 缓存性能提升不明显")

def main():
    """主测试函数"""
    print("开始测试弹幕缓存机制...")
    
    try:
        # 测试DanmuClient缓存
        test_danmu_client_cache()
        
        # 测试缓存性能提升
        test_cache_performance()
        
        print("\n=== 测试完成 ===")
        print("缓存机制测试已完成，请查看上述输出结果")
        print("\n总结:")
        print("- 作品列表缓存: 避免重复请求/api/control/library")
        print("- 弹幕源缓存: 处理同一视频不同集数时复用数据")
        print("- 分集列表缓存: 减少重复的分集信息请求")
        print("- 缓存TTL: 作品列表5分钟，弹幕源和分集列表10分钟")
        
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()