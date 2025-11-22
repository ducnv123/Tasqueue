# Docker Deployment Guide

Hướng dẫn chạy Tasqueue Python với Docker và Docker Compose.

## 📦 Yêu cầu

- Docker >= 20.10
- Docker Compose >= 2.0

## 🚀 Quick Start

### 1. Build và chạy với docker-compose

```bash
cd python

# Build và start tất cả services
docker-compose up -d

# Xem logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop và xóa volumes (data sẽ mất)
docker-compose down -v
```

### 2. Chạy worker riêng lẻ

```bash
# Build image
docker build -t tasqueue-python .

# Chạy với Redis local
docker run -it --rm \
  -e REDIS_HOST=host.docker.internal \
  -e REDIS_PORT=6379 \
  tasqueue-python \
  python examples/redis_example.py
```

## 🏗️ Cấu trúc Services

### Services trong docker-compose.yml:

1. **redis** - Message broker và results backend
   - Port: 6379
   - Data persistence với volume
   - Health check enabled

2. **tasqueue-worker** - Worker process
   - Auto-restart
   - Depends on Redis health
   - Sử dụng config.docker.yaml

## ⚙️ Configuration

### Environment Variables

```bash
# .env file (tạo file này nếu cần)
TASQUEUE_ENV=production
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_password_here

# Load .env trong docker-compose
docker-compose --env-file .env up
```

### Config Files

- `config.yaml` - Config mặc định (cho local dev)
- `config.docker.yaml` - Config cho Docker (Redis host = "redis")

Trong Docker, sử dụng `config.docker.yaml`:

```yaml
broker:
  type: redis
  redis:
    host: redis  # Docker service name
    port: 6379
```

## 📊 Monitoring

### Xem logs

```bash
# Tất cả services
docker-compose logs -f

# Chỉ worker
docker-compose logs -f tasqueue-worker

# Chỉ Redis
docker-compose logs -f redis
```

### Kiểm tra Redis

```bash
# Connect vào Redis container
docker-compose exec redis redis-cli

# Trong redis-cli:
> PING
> KEYS tasqueue:*
> LLEN tasqueue:queue:tasqueue:tasks
```

### Health Check

```bash
# Kiểm tra status của services
docker-compose ps

# Kiểm tra health của Redis
docker-compose exec redis redis-cli ping
```

## 🔧 Development Workflow

### Local Development với Docker

```bash
# Chỉ chạy Redis, code chạy local
docker-compose up -d redis

# Chạy code local
export REDIS_HOST=localhost
python examples/redis_example.py
```

### Live Reload với Volumes

Docker-compose đã mount source code:

```yaml
volumes:
  - ./tasqueue:/app/tasqueue
  - ./examples:/app/examples
```

Khi sửa code, restart worker:

```bash
docker-compose restart tasqueue-worker
```

## 🏭 Production Deployment

### Multi-Worker Setup

```yaml
# docker-compose.prod.yml
services:
  tasqueue-worker:
    deploy:
      replicas: 3  # 3 workers
    environment:
      - TASQUEUE_ENV=production
```

Chạy:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Resource Limits

```yaml
services:
  tasqueue-worker:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### Security Best Practices

1. **Không hardcode passwords** trong docker-compose.yml:

```yaml
environment:
  - REDIS_PASSWORD=${REDIS_PASSWORD}
```

2. **Sử dụng secrets** (Docker Swarm):

```yaml
secrets:
  redis_password:
    external: true

services:
  tasqueue-worker:
    secrets:
      - redis_password
    environment:
      - REDIS_PASSWORD_FILE=/run/secrets/redis_password
```

3. **Network isolation**:

```yaml
networks:
  tasqueue-network:
    internal: true  # Không expose ra internet
```

## 🐛 Troubleshooting

### Worker không connect được Redis

```bash
# Kiểm tra Redis có chạy không
docker-compose ps redis

# Kiểm tra logs Redis
docker-compose logs redis

# Test connection
docker-compose exec tasqueue-worker ping redis
```

### Memory issues

```bash
# Xem resource usage
docker stats

# Tăng memory limit
docker-compose up -d --scale tasqueue-worker=2
```

### Clean up everything

```bash
# Stop tất cả
docker-compose down

# Xóa images
docker-compose down --rmi all

# Xóa volumes (DATA MẤT HẾT!)
docker-compose down -v

# Xóa tất cả
docker-compose down -v --rmi all
```

## 🔄 Update và Rebuild

```bash
# Pull latest code
git pull

# Rebuild image
docker-compose build

# Restart với image mới
docker-compose up -d

# Hoặc rebuild và restart cùng lúc
docker-compose up -d --build
```

## 📈 Scaling

### Scale workers

```bash
# Scale to 5 workers
docker-compose up -d --scale tasqueue-worker=5

# Scale down to 2 workers
docker-compose up -d --scale tasqueue-worker=2
```

### Load Balancing với HAProxy

```yaml
# docker-compose.lb.yml
services:
  haproxy:
    image: haproxy:latest
    ports:
      - "8080:8080"
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg
    depends_on:
      - tasqueue-worker
```

## 🎯 Custom Commands

### Run một task cụ thể

```bash
docker-compose run --rm tasqueue-worker \
  python -c "from examples.redis_example import main; import asyncio; asyncio.run(main())"
```

### Interactive shell

```bash
docker-compose run --rm tasqueue-worker bash
```

### Python REPL

```bash
docker-compose run --rm tasqueue-worker python
```

## 📝 Example docker-compose Override

Tạo `docker-compose.override.yml` cho local dev:

```yaml
version: '3.8'

services:
  tasqueue-worker:
    volumes:
      - ./:/app  # Mount toàn bộ
    environment:
      - TASQUEUE_ENV=development
    command: python examples/memory_example.py
```

File này tự động được load bởi docker-compose!

## 🌐 Docker Hub

### Build và push image

```bash
# Build
docker build -t yourusername/tasqueue-python:latest .

# Tag version
docker tag yourusername/tasqueue-python:latest yourusername/tasqueue-python:v2.0.0

# Push
docker push yourusername/tasqueue-python:latest
docker push yourusername/tasqueue-python:v2.0.0
```

### Sử dụng từ Docker Hub

```yaml
services:
  tasqueue-worker:
    image: yourusername/tasqueue-python:v2.0.0
    # không cần build
```

---

## 🎉 Complete Example

```bash
# 1. Clone repo
git clone https://github.com/yourusername/tasqueue.git
cd tasqueue/python

# 2. Tạo config
cp config.yaml config.docker.yaml
# Edit config.docker.yaml - đổi host thành "redis"

# 3. Start services
docker-compose up -d

# 4. Xem logs
docker-compose logs -f tasqueue-worker

# 5. Scale workers
docker-compose up -d --scale tasqueue-worker=3

# 6. Monitor Redis
docker-compose exec redis redis-cli
> KEYS tasqueue:*

# 7. Clean up
docker-compose down -v
```

Vậy là xong! 🚀
