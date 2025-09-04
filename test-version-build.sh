#!/bin/bash
# 测试自动版本生成的本地构建脚本

# 设置版本信息
VERSION="1.0.8"
BUILD_DATE=$(date -u +"%Y-%m-%d")

echo "构建版本: $VERSION"
echo "构建日期: $BUILD_DATE"

# 构建 Docker 镜像
docker build \
  --build-arg VERSION=$VERSION \
  --build-arg BUILD_DATE=$BUILD_DATE \
  -t subtitle-test:$VERSION \
  .

echo "构建完成！"
echo "运行以下命令来测试镜像:"
echo "docker run -p 5000:5000 subtitle-test:$VERSION"