# 弹幕客户端新版API使用说明

## 概述

新版API基于四个控制接口实现了完整的弹幕获取流程，支持根据作品标题、季数和集数精确获取弹幕数据。

## 新增API方法

### 1. 获取作品列表
```python
client = DanmuClient()
result = client.get_library_list()
if result['success']:
    animes = result['animes']
    for anime in animes:
        print(f"作品: {anime['title']} (ID: {anime['animeId']}, 第{anime['season']}季)")
```

### 2. 获取弹幕源列表
```python
sources_result = client.get_anime_sources(anime_id=41)
if sources_result['success']:
    sources = sources_result['sources']
    for source in sources:
        print(f"弹幕源: {source['providerName']} (ID: {source['sourceId']})")
```

### 3. 获取分集列表
```python
episodes_result = client.get_source_episodes(source_id=156)
if episodes_result['success']:
    episodes = episodes_result['episodes']
    for episode in episodes:
        print(f"第{episode['episodeIndex']}集: {episode['title']} (ID: {episode['episodeId']})")
```

### 4. 获取弹幕数据
```python
danmaku_result = client.get_episode_danmaku(episode_id="25000041010001")
if danmaku_result['success']:
    danmaku = danmaku_result['danmaku']
    print(f"弹幕数量: {danmaku['count']}")
    for comment in danmaku['comments'][:5]:  # 显示前5条
        print(f"弹幕: {comment['m']}")
```

### 5. 一键获取弹幕（推荐使用）
```python
# 根据作品标题、季数和集数直接获取弹幕
danmaku_data = client.get_danmaku_by_title_and_episode(
    title="沧元图",
    season=1,
    episode_index=1
)

if danmaku_data:
    print(f"获取到 {danmaku_data['count']} 条弹幕")
    comments = danmaku_data['comments']
    for comment in comments[:10]:  # 显示前10条
        print(f"弹幕内容: {comment['m']}")
else:
    print("未找到匹配的弹幕数据")
```

## 配置要求

确保配置文件中包含正确的API地址和密钥：

```json
{
    "danmu_api": {
        "base_url": "https://danmu.dolast.top:10010",
        "api_key": "your_api_key_here"
    }
}
```

## 测试结果

- ✅ 成功获取28个作品列表
- ✅ 成功匹配《沧元图》第1季
- ✅ 成功获取1个弹幕源（youku）
- ✅ 成功获取59个分集
- ✅ 成功获取6539条弹幕数据

## 错误处理

所有API方法都包含完善的错误处理：
- 自动重试机制
- 详细的错误日志
- 标准化的返回格式
- 配置验证

## 兼容性

新版API与旧版API完全兼容，旧版方法仍然可用（虽然当前服务器返回HTML页面）。