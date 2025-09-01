# Docker 部署指南

本指南将帮助您将字幕处理应用打包成Docker镜像并部署。

## 1. 构建Docker镜像

### 基本构建命令
```bash
# 在项目根目录下执行
docker build -t subtitle-processor:latest .
```

### 带版本标签的构建
```bash
# 构建带版本号的镜像
docker build -t subtitle-processor:v1.0.0 .

# 同时打上latest标签
docker tag subtitle-processor:v1.0.0 subtitle-processor:latest
```

## 2. 运行Docker容器

### 基本运行命令
```bash
# 运行容器，映射端口5000
docker run -d \
  --name subtitle-app \
  -p 5000:5000 \
  subtitle-processor:latest
```

### 带数据卷挂载的运行
```bash
# 挂载本地目录到容器，用于处理字幕文件
docker run -d \
  --name subtitle-app \
  -p 5000:5000 \
  -v /path/to/your/subtitles:/app/subtitles \
  -v /path/to/logs:/app/logs \
  subtitle-processor:latest
```

### Windows环境下的运行
```powershell
# PowerShell命令
docker run -d `
  --name subtitle-app `
  -p 5000:5000 `
  -v "D:\your\subtitle\folder:/app/subtitles" `
  -v "D:\your\logs\folder:/app/logs" `
  subtitle-processor:latest
```

## 3. 容器管理命令

### 查看容器状态
```bash
# 查看运行中的容器
docker ps

# 查看所有容器（包括停止的）
docker ps -a

# 查看容器日志
docker logs subtitle-app

# 实时查看日志
docker logs -f subtitle-app
```

### 容器操作
```bash
# 停止容器
docker stop subtitle-app

# 启动容器
docker start subtitle-app

# 重启容器
docker restart subtitle-app

# 删除容器
docker rm subtitle-app

# 强制删除运行中的容器
docker rm -f subtitle-app
```

### 进入容器调试
```bash
# 进入容器内部
docker exec -it subtitle-app /bin/bash

# 或者使用sh（如果bash不可用）
docker exec -it subtitle-app /bin/sh
```

## 4. Docker Compose 部署（推荐）

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  subtitle-processor:
    build: .
    container_name: subtitle-app
    ports:
      - "5000:5000"
    volumes:
      - ./subtitles:/app/subtitles
      - ./logs:/app/logs
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/status"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Docker Compose 命令
```bash
# 构建并启动服务
docker-compose up -d

# 重新构建并启动
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

## 5. 生产环境部署

### 使用反向代理（Nginx）

创建 `nginx.conf`：
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 完整的生产环境 docker-compose.yml
```yaml
version: '3.8'

services:
  subtitle-processor:
    build: .
    container_name: subtitle-app
    expose:
      - "5000"
    volumes:
      - ./subtitles:/app/subtitles
      - ./logs:/app/logs
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
    networks:
      - subtitle-network

  nginx:
    image: nginx:alpine
    container_name: subtitle-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl  # SSL证书目录
    depends_on:
      - subtitle-processor
    restart: unless-stopped
    networks:
      - subtitle-network

networks:
  subtitle-network:
    driver: bridge
```

## 6. 镜像管理

### 推送到Docker Hub
```bash
# 登录Docker Hub
docker login

# 标记镜像
docker tag subtitle-processor:latest yourusername/subtitle-processor:latest

# 推送镜像
docker push yourusername/subtitle-processor:latest
```

### 推送到私有仓库
```bash
# 标记镜像
docker tag subtitle-processor:latest your-registry.com/subtitle-processor:latest

# 推送镜像
docker push your-registry.com/subtitle-processor:latest
```

## 7. 监控和维护

### 查看资源使用情况
```bash
# 查看容器资源使用
docker stats subtitle-app

# 查看镜像大小
docker images subtitle-processor
```

### 清理Docker资源
```bash
# 清理未使用的镜像
docker image prune

# 清理未使用的容器
docker container prune

# 清理所有未使用的资源
docker system prune
```

## 8. 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   # 查看端口占用
   netstat -tulpn | grep 5000
   # 或使用不同端口
   docker run -p 8080:5000 subtitle-processor:latest
   ```

2. **权限问题**
   ```bash
   # 确保挂载目录有正确权限
   chmod 755 /path/to/subtitles
   chown -R 1000:1000 /path/to/subtitles
   ```

3. **容器无法启动**
   ```bash
   # 查看详细错误信息
   docker logs subtitle-app
   
   # 交互式运行调试
   docker run -it --rm subtitle-processor:latest /bin/bash
   ```

## 9. 自动化部署脚本

创建 `deploy.sh`：
```bash
#!/bin/bash

# 停止并删除旧容器
docker stop subtitle-app 2>/dev/null || true
docker rm subtitle-app 2>/dev/null || true

# 构建新镜像
docker build -t subtitle-processor:latest .

# 运行新容器
docker run -d \
  --name subtitle-app \
  -p 5000:5000 \
  -v "$(pwd)/subtitles:/app/subtitles" \
  -v "$(pwd)/logs:/app/logs" \
  --restart unless-stopped \
  subtitle-processor:latest

echo "部署完成！应用已在 http://localhost:5000 启动"
```

使用方法：
```bash
chmod +x deploy.sh
./deploy.sh
```

## 访问应用

部署完成后，您可以通过以下方式访问应用：
- Web界面: http://localhost:5000
- API接口: http://localhost:5000/api/status

根据您的具体需求选择合适的部署方式。推荐使用Docker Compose进行部署，它提供了更好的配置管理和服务编排能力。