FROM python:3.8-slim

# 定义构建参数
ARG VERSION=1.0.0
ARG BUILD_DATE=2024-01-01

WORKDIR /app

# 复制依赖文件并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 动态更新版本信息
RUN sed -i "s/__version__ = \".*\"/__version__ = \"${VERSION}\"/g" version.py && \
    sed -i "s/__build_date__ = \".*\"/__build_date__ = \"${BUILD_DATE}\"/g" version.py

# 创建必要目录
RUN mkdir -p logs
RUN mkdir -p videos
RUN mkdir -p test_videos
RUN mkdir -p config

# 创建默认配置文件到config目录
RUN echo '{ \
  "watch_dirs": ["./videos", "./test_videos"], \
  "file_extensions": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"], \
  "wait_time": 0.5, \
  "max_retries": 3, \
  "retry_delay": 1.0, \
  "enable_logging": true, \
  "log_level": "INFO", \
  "max_log_lines": 5000, \
  "keep_log_lines": 2000, \
  "cron_schedule": "0 5 * * *", \
  "cron_enabled": false, \
  "danmu_api": { \
    "base_url": "", \
    "token": "" \
  } \
}' > config/config.json

# 暴露应用端口
EXPOSE 5000

# 设置环境变量
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 启动应用
CMD ["python", "app.py"]