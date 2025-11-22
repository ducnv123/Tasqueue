# Configuration Guide

Tasqueue Python hỗ trợ cấu hình qua file YAML, giúp quản lý settings dễ dàng và linh hoạt.

## 1. Cấu trúc Config File

File `config.yaml` chứa tất cả cấu hình cho hệ thống:

```yaml
# Broker configuration
broker:
  type: redis  # hoặc 'memory'
  redis:
    host: localhost
    port: 6379
    db: 0
    password: null

# Results backend configuration
results:
  type: redis  # hoặc 'memory'
  redis:
    host: localhost
    port: 6379
    db: 0
    password: null

# Server configuration
server:
  default_concurrency: 4
  log_level: INFO

# Job defaults
job_defaults:
  max_retries: 3
  timeout_seconds: 300
```

## 2. Environment-specific Config

Bạn có thể override config cho từng environment:

```yaml
# Base config
broker:
  type: redis
  redis:
    host: localhost

# Development overrides
development:
  broker:
    type: memory  # Dùng in-memory cho dev
  server:
    log_level: DEBUG
```

## 3. Sử Dụng trong Code

### 3.1. Load Config

```python
from tasqueue.config import init_config, get_config

# Load config file
config = init_config('config.yaml')

# Hoặc load với environment cụ thể
config = init_config('config.yaml', env='development')

# Hoặc dùng biến môi trường TASQUEUE_ENV
# export TASQUEUE_ENV=development
config = init_config('config.yaml')
```

### 3.2. Sử Dụng Factory để tạo Broker/Results

```python
from tasqueue.factory import create_broker_from_config, create_results_from_config

# Tạo broker và results từ config
broker = create_broker_from_config()
results = create_results_from_config()
```

### 3.3. Truy xuất Config Values

```python
from tasqueue.config import get_config

config = get_config()

# Dùng dot notation
host = config.get('broker.redis.host')
port = config.get('broker.redis.port', 6379)  # với default value

# Hoặc dùng dict-like access
host = config['broker.redis.host']

# Lấy config theo nhóm
broker_config = config.get_broker_config()
server_config = config.get_server_config()
job_defaults = config.get_job_defaults()
```

### 3.4. Full Example

```python
import asyncio
from tasqueue import Server, ServerOpts
from tasqueue.config import init_config
from tasqueue.factory import create_broker_from_config, create_results_from_config

async def main():
    # 1. Load config
    config = init_config('config.yaml', env='development')

    # 2. Create components from config
    broker = create_broker_from_config()
    results = create_results_from_config()

    # 3. Create server
    server = Server(ServerOpts(
        broker=broker,
        results=results
    ))

    # 4. Use config values
    default_conc = config.get('server.default_concurrency', 4)

    # ... register tasks and run server

asyncio.run(main())
```

## 4. Config File Locations

Config sẽ được tự động tìm kiếm ở các vị trí sau (theo thứ tự):

1. `./config.yaml` (thư mục hiện tại)
2. `./config/config.yaml`
3. `../config.yaml` (thư mục cha)
4. `~/.tasqueue/config.yaml` (home directory)
5. `/etc/tasqueue/config.yaml` (system-wide)

Hoặc bạn có thể chỉ định path cụ thể:

```python
config = init_config('/path/to/custom/config.yaml')
```

## 5. Environment Variables

Sử dụng biến môi trường để chọn environment:

```bash
# Linux/Mac
export TASQUEUE_ENV=production
python app.py

# Windows
set TASQUEUE_ENV=production
python app.py
```

## 6. Best Practices

### 6.1. Tách Config theo Environment

```yaml
# config.yaml
broker:
  type: redis
  redis:
    host: redis-prod.example.com
    port: 6379

# Development override
development:
  broker:
    type: memory  # Không cần Redis khi dev
  server:
    log_level: DEBUG

# Testing override
testing:
  broker:
    type: memory
  results:
    type: memory
```

### 6.2. Sensitive Data

Không commit sensitive data vào git. Dùng environment variables:

```yaml
broker:
  redis:
    host: ${REDIS_HOST:localhost}
    password: ${REDIS_PASSWORD:null}
```

### 6.3. Config Template

Tạo `config.example.yaml` để commit vào git:

```yaml
# config.example.yaml
broker:
  type: redis
  redis:
    host: localhost
    port: 6379
    password: YOUR_PASSWORD_HERE
```

Và add `config.yaml` vào `.gitignore`:

```
config.yaml
```

## 7. Complete Config Reference

```yaml
# Broker Configuration
broker:
  type: redis  # redis | memory
  redis:
    host: localhost
    port: 6379
    db: 0
    password: null
    max_connections: 10
    socket_timeout: null
    socket_connect_timeout: 5.0

# Results Configuration
results:
  type: redis  # redis | memory
  redis:
    host: localhost
    port: 6379
    db: 0
    password: null
    max_connections: 10
    socket_timeout: null
    socket_connect_timeout: 5.0

# Server Configuration
server:
  default_concurrency: 4
  log_level: INFO
  log_format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Queue Configuration
queues:
  default:
    name: tasqueue:tasks
    concurrency: 4

  high_priority:
    name: tasqueue:high
    concurrency: 10

  low_priority:
    name: tasqueue:low
    concurrency: 2

# Job Defaults
job_defaults:
  max_retries: 3
  timeout_seconds: 300

# Environment Overrides
development:
  broker:
    type: memory
  results:
    type: memory
  server:
    log_level: DEBUG

production:
  server:
    log_level: WARNING

testing:
  broker:
    type: memory
  results:
    type: memory
```

## 8. Migration Guide

Nếu bạn đang dùng cách cũ (truyền params trực tiếp), migration sang config file:

### Trước:

```python
from tasqueue.brokers.redis_broker import RedisBroker
from tasqueue.results.redis_results import RedisResults

broker = RedisBroker(
    host="localhost",
    port=6379,
    db=0,
    password="secret"
)

results = RedisResults(
    host="localhost",
    port=6379,
    db=0,
    password="secret"
)
```

### Sau:

**config.yaml:**
```yaml
broker:
  type: redis
  redis:
    host: localhost
    port: 6379
    db: 0
    password: secret

results:
  type: redis
  redis:
    host: localhost
    port: 6379
    db: 0
    password: secret
```

**Code:**
```python
from tasqueue.config import init_config
from tasqueue.factory import create_broker_from_config, create_results_from_config

init_config('config.yaml')
broker = create_broker_from_config()
results = create_results_from_config()
```

Đơn giản và dễ quản lý hơn nhiều! 🎉
