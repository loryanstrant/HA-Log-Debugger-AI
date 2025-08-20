# 🏠 HA Log Debugger AI

A comprehensive Docker container that monitors Home Assistant logs in real-time and provides AI-powered recommendations for warnings and errors using OpenAI-compatible APIs.

## ✨ Features

- **Real-time Log Monitoring**: Watches Home Assistant log files for new entries using file system events
- **AI-Powered Analysis**: Uses OpenAI-compatible APIs to analyze errors and provide actionable recommendations
- **Web Interface**: Clean, responsive web UI to view logs, recommendations, and system status
- **Smart Filtering**: Avoids duplicate analysis by tracking processed log entries
- **Multi-Architecture Support**: Works on both x86_64 and ARM64 (Raspberry Pi) systems
- **Health Monitoring**: Built-in health checks and system status monitoring
- **Persistent Storage**: SQLite database to store recommendations and processed logs

## 🚀 Quick Start

### Docker Compose (Recommended)

1. Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  ha-log-debugger-ai:
    image: ghcr.io/loryanstrant/ha-log-debugger-ai:latest
    container_name: ha-log-debugger-ai
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - /path/to/homeassistant/config:/config:ro
      - ./data:/data
    environment:
      - OPENAI_ENDPOINT_URL=https://api.openai.com/v1
      - OPENAI_API_KEY=your_api_key_here
      - MODEL_NAME=gpt-3.5-turbo
      - TZ=America/New_York
```

2. Replace `/path/to/homeassistant/config` with your actual Home Assistant config directory
3. Set your OpenAI API key and endpoint URL
4. Run: `docker-compose up -d`
5. Access the web interface at `http://localhost:8080`

### Docker Run

```bash
docker run -d \
  --name ha-log-debugger-ai \
  -p 8080:8080 \
  -v /path/to/homeassistant/config:/config:ro \
  -v ./data:/data \
  -e OPENAI_ENDPOINT_URL=https://api.openai.com/v1 \
  -e OPENAI_API_KEY=your_api_key_here \
  ghcr.io/loryanstrant/ha-log-debugger-ai:latest
```

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_ENDPOINT_URL` | ✅ | - | OpenAI-compatible API endpoint URL |
| `OPENAI_API_KEY` | ✅ | - | API key for the AI service |
| `MODEL_NAME` | ❌ | `gpt-3.5-turbo` | Preferred LLM model name |
| `TZ` | ❌ | `UTC` | Time zone for log timestamps |
| `HA_CONFIG_PATH` | ❌ | `/config` | Path to Home Assistant config directory |
| `LOG_LEVEL` | ❌ | `INFO` | Application log level (DEBUG, INFO, WARNING, ERROR) |
| `WEB_PORT` | ❌ | `8080` | Web interface port |

### Volume Mounts

- `/config` - Home Assistant configuration directory (read-only)
- `/data` - Data directory for SQLite database and application data

## 🖥️ Web Interface

The web interface provides three main tabs:

### Recommendations
- View AI-generated recommendations for log issues
- Filter by severity level (Critical, High, Medium, Low)
- Mark recommendations as resolved
- Expand/collapse detailed recommendations

### Recent Logs
- View recent log entries from Home Assistant
- Filter by number of lines to display
- Color-coded log levels for easy identification

### Statistics
- System health status
- Database statistics
- Service availability status

## 🔧 API Endpoints

The application exposes a REST API for integration:

- `GET /api/health` - System health status
- `GET /api/recommendations` - Get all recommendations
- `GET /api/recommendations?resolved=false` - Get unresolved recommendations
- `POST /api/recommendations/{id}/resolve` - Mark recommendation as resolved
- `GET /api/logs/recent?lines=100` - Get recent log entries
- `GET /api/stats` - Get application statistics
- `POST /api/analyze` - Manually trigger log analysis

## 🛠️ Development

### Prerequisites

- Python 3.11+
- Docker (for containerization)
- OpenAI-compatible API access

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/loryanstrant/HA-Log-Debugger-AI.git
cd HA-Log-Debugger-AI
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables:
```bash
export OPENAI_ENDPOINT_URL="https://api.openai.com/v1"
export OPENAI_API_KEY="your_api_key"
export HA_CONFIG_PATH="/path/to/ha/config"
```

4. Run the application:
```bash
python -m src.main
```

### Building Docker Image

```bash
docker build -t ha-log-debugger-ai .
```

## 🏗️ Architecture

The application consists of several components:

- **Log Monitor**: Uses Watchdog to monitor Home Assistant log files for changes
- **AI Analyzer**: Processes log entries through OpenAI-compatible APIs
- **Database**: SQLite database for storing recommendations and tracking processed logs
- **Web Interface**: FastAPI-based web server with HTML/CSS/JavaScript frontend
- **Main Orchestrator**: Coordinates all services and handles graceful shutdown

## 🐛 Troubleshooting

### Common Issues

1. **"Log file not found"**
   - Ensure the Home Assistant config directory is correctly mounted
   - Check that `home-assistant.log` exists in the config directory

2. **"AI service connection failed"**
   - Verify your OpenAI endpoint URL and API key
   - Check internet connectivity from the container
   - Ensure the API endpoint is reachable

3. **"Permission denied"**
   - Ensure the mounted volumes have correct permissions
   - The container runs as a non-root user (`appuser`)

4. **High CPU usage**
   - Consider adjusting the log monitoring frequency
   - Check if there are too many log entries being processed

### Logs

Check container logs for debugging:
```bash
docker logs ha-log-debugger-ai
```

Enable debug logging:
```bash
docker run ... -e LOG_LEVEL=DEBUG ...
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Home Assistant community for inspiration
- OpenAI for providing the AI capabilities
- FastAPI and all the other amazing Python libraries used in this project
