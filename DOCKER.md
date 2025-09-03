# Docker Deployment Guide

This guide explains how to deploy CLADS LLM Bridge using Docker and Docker Compose.

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository-url>
   cd clads-llm-bridge
   ```

2. **Start the application:**
   ```bash
   docker-compose up -d
   ```

3. **Access the application:**
   - Configuration UI: http://localhost:4322
   - LLM Proxy API: http://localhost:4321
   - Default password: `Hakodate4`

### Using Docker Build

1. **Build the image:**
   ```bash
   docker build -t clads-llm-bridge .
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     --name clads-llm-bridge \
     -p 4321:4321 \
     -p 4322:4322 \
     -v clads_data:/app/data \
     clads-llm-bridge
   ```

## Configuration

### Environment Variables

The application supports the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_UI_PORT` | `4322` | Port for the configuration web UI |
| `PROXY_PORT` | `4321` | Port for the LLM proxy server |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DATABASE_PATH` | `/app/data/clads_llm_bridge.db` | SQLite database file path |
| `DATA_DIR` | `/app/data` | Data directory for persistent storage |
| `INITIAL_PASSWORD` | `Hakodate4` | Initial admin password |
| `SESSION_SECRET_KEY` | (auto-generated) | Secret key for session management |
| `ENCRYPTION_KEY_PATH` | `/app/data/.encryption_key` | Path to encryption key file |
| `LITELLM_LOG` | `INFO` | LiteLLM logging level |
| `LITELLM_DROP_PARAMS` | `true` | Drop unsupported parameters in LiteLLM |

### Using Environment Files

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file with your settings:**
   ```bash
   nano .env
   ```

3. **Start with environment file:**
   ```bash
   docker-compose --env-file .env up -d
   ```

## Deployment Scenarios

### Development Deployment

For development, use the default docker-compose configuration:

```bash
docker-compose up
```

This will:
- Mount the local `./data` directory for easy access
- Use development-friendly logging
- Allow easy container rebuilding

### Production Deployment

For production, use the production compose file:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

This will:
- Use named volumes for data persistence
- Apply resource limits
- Use production logging configuration
- Set stricter restart policies

### Custom Port Configuration

To use different ports:

```bash
WEB_UI_PORT=8080 PROXY_PORT=8081 docker-compose up -d
```

Or modify your `.env` file:
```env
WEB_UI_PORT=8080
PROXY_PORT=8081
```

## Data Persistence

### Named Volumes (Recommended for Production)

The default configuration uses Docker named volumes:

```yaml
volumes:
  clads_data:/app/data
```

To backup data:
```bash
docker run --rm -v clads_data:/data -v $(pwd):/backup alpine tar czf /backup/clads_backup.tar.gz -C /data .
```

To restore data:
```bash
docker run --rm -v clads_data:/data -v $(pwd):/backup alpine tar xzf /backup/clads_backup.tar.gz -C /data
```

### Local Directory Mounts (Development)

For development, you can mount a local directory:

```yaml
volumes:
  - ./data:/app/data
```

## Health Checks

The container includes built-in health checks:

- **Endpoint:** `http://localhost:4322/health`
- **Interval:** 30 seconds
- **Timeout:** 10 seconds
- **Retries:** 3
- **Start Period:** 40 seconds

Check container health:
```bash
docker ps
docker inspect clads-llm-bridge | grep Health -A 10
```

## Monitoring and Logs

### View Logs

```bash
# All logs
docker-compose logs

# Follow logs
docker-compose logs -f

# Specific service logs
docker-compose logs clads-llm-bridge
```

### Resource Monitoring

```bash
# Container stats
docker stats clads-llm-bridge

# Resource usage
docker system df
```

## Troubleshooting

### Common Issues

1. **Port conflicts:**
   ```bash
   # Check what's using the ports
   lsof -i :4321
   lsof -i :4322
   
   # Use different ports
   WEB_UI_PORT=5322 PROXY_PORT=5321 docker-compose up -d
   ```

2. **Permission issues:**
   ```bash
   # Fix data directory permissions
   sudo chown -R 1000:1000 ./data
   ```

3. **Database corruption:**
   ```bash
   # Remove and recreate database
   docker-compose down
   docker volume rm clads_data
   docker-compose up -d
   ```

### Debug Mode

Enable debug logging:

```bash
LOG_LEVEL=DEBUG docker-compose up
```

### Container Shell Access

Access the running container:

```bash
docker exec -it clads-llm-bridge /bin/bash
```

## Security Considerations

### Network Security

- The application binds to `0.0.0.0` inside the container
- Only expose necessary ports to the host
- Use a reverse proxy (nginx, traefik) for production

### Data Security

- API keys are encrypted and stored in the database
- Change the default password immediately
- Use strong session secret keys in production
- Regularly backup your data

### Production Hardening

1. **Use a reverse proxy:**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:4322;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. **Enable HTTPS:**
   - Use Let's Encrypt certificates
   - Configure SSL termination at the reverse proxy

3. **Network isolation:**
   ```yaml
   networks:
     clads_network:
       driver: bridge
   ```

## Updating

### Update the Application

1. **Pull latest changes:**
   ```bash
   git pull origin main
   ```

2. **Rebuild and restart:**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Backup Before Updates

Always backup your data before updating:

```bash
docker run --rm -v clads_data:/data -v $(pwd):/backup alpine tar czf /backup/backup-$(date +%Y%m%d).tar.gz -C /data .
```

## Support

For issues and questions:
- Check the application logs: `docker-compose logs`
- Verify health status: `curl http://localhost:4322/health`
- Review the configuration in the web UI
- Check resource usage: `docker stats`