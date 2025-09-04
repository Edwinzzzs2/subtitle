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

# 创建日志目录
RUN mkdir -p logs

# 创建视频存储目录
RUN mkdir -p videos

# 暴露应用端口
EXPOSE 5000

# 设置环境变量
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 启动应用
CMD ["python", "app.py"]