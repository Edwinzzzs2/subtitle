# 版本信息配置文件
# 每次发布新版本时更新此文件

__version__ = "1.0.6"
__build_date__ = "2024-12-12"
__description__ = "视频文件监听器 - 自动生成弹幕字幕"

def get_version_info():
    """获取版本信息"""
    return {
        "version": __version__,
        "build_date": __build_date__,
        "description": __description__
    }