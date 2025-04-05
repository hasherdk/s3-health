# S3 Health

S3 Health is a lightweight application designed to monitor the health and availability of Amazon S3 or similar buckets, like MinIO. It can be used as a sidecar container alongside monitoring tools like Uptime Kuma to provide comprehensive visibility into your S3 infrastructure.

## Overview

This service performs health checks on configured S3 buckets by:
- Verifying bucket accessibility
- Checking the age of the newest object in the bucket
- Providing a simple REST API for health status

## Features

- Real-time S3 bucket health monitoring
- Customizable age thresholds for newest objects
- Simple HTTP API for integration with monitoring tools
- Low resource footprint suitable for sidecar deployment
- Compatible with S3-compatible storage services via custom endpoints

## Prerequisites

- Docker (for containerized deployment)
- S3 bucket access credentials
- Optional: Uptime Kuma or similar monitoring tool

## Quick Start

### Running with Docker

```bash
docker run -d \
  -e S3_KEY=your_access_key \
  -e S3_SECRET=your_secret_key \
  -e S3_ENDPOINT=https://s3.amazonaws.com \
  -p 8000:8000 \
  s3-health:latest
```

### Running locally

```bash
git clone https://github.com/yourusername/s3-health.git
cd s3-health
pip install -r requirements.txt
python src/main.py
```

## Configuration

Configure S3 Health using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `S3_KEY` | AWS access key ID with S3 permissions | - |
| `S3_SECRET` | AWS secret access key | - |
| `S3_ENDPOINT` | S3 endpoint URL | https://s3.amazonaws.com |

## API Usage

### Check Bucket Health

```
GET /health/{bucket_name}?max_age=24h
```

Parameters:
- `bucket_name`: Name of the S3 bucket to check
- `max_age`: Maximum age of newest object (format: 24h, 30m, 1d), defaults to 24h

Response:
- Status 200: Bucket health is good, returns newest object details
- Status 500: Health check failed with detailed reason
- Status 400: Invalid request parameters

Example successful response:
```json
{
  "status": "ok",
  "newest_object": {
    "key": "backups/2023-04-01.zip",
    "last_modified": "2023-04-01T12:00:00+00:00",
    "age_seconds": 3600
  }
}
```

## Integration with Uptime Kuma

[Uptime Kuma](https://github.com/louislam/uptime-kuma) is a popular open-source monitoring tool. Here's how to integrate S3 Health with it:

1. Deploy S3 Health as a sidecar container alongside your Uptime Kuma instance
2. In Uptime Kuma, add a new monitor with the following settings:
   - **Monitor Type**: HTTP(s)
   - **URL**: `http://s3-health:8000/health/your-bucket-name?max_age=24h`
   - **Method**: GET
   - **Follow Redirects**: Yes
   - **Accept Status Codes**: 200
   - Set your desired notification settings

### Docker Compose Example with Uptime Kuma

```yaml
version: '3'
services:
  uptime-kuma:
    image: louislam/uptime-kuma:latest
    ports:
      - "3001:3001"
    volumes:
      - uptime-kuma-data:/app/data
    restart: always

  s3-health:
    image: ghcr.io/hasherdk/s3-health:latest
    environment:
      - S3_KEY=your_access_key
      - S3_SECRET=your_secret_key
      - S3_ENDPOINT=https://s3.amazonaws.com
    restart: always

volumes:
  uptime-kuma-data:
```


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License
This project is licensed under the GPLv3 License - see the [LICENSE](LICENSE) file for details.
