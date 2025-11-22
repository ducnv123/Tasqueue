#!/bin/bash
set -e

# Wait for Redis to be ready
if [ "$REDIS_HOST" ]; then
    echo "Waiting for Redis at $REDIS_HOST:$REDIS_PORT..."

    max_attempts=30
    attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if python -c "import redis; r=redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT); r.ping()" 2>/dev/null; then
            echo "Redis is ready!"
            break
        fi

        attempt=$((attempt + 1))
        echo "Waiting for Redis... (attempt $attempt/$max_attempts)"
        sleep 1
    done

    if [ $attempt -eq $max_attempts ]; then
        echo "Error: Redis not available after $max_attempts attempts"
        exit 1
    fi
fi

# Execute the main command
exec "$@"
