# Docker Installation Instructions

## Prerequisites

Before you begin, make sure you have Docker Desktop installed on your system:

- **Windows/Mac**: Download from [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
- **Linux**: Follow instructions at [https://docs.docker.com/engine/install/](https://docs.docker.com/engine/install/)

## Installation Options

You have two options to run this application:

### Option 1: Using Docker Image (Recommended for End Users)

#### Step 1: Load the Docker Image

If you received a `.tar` file:

```bash
docker load -i dnit-pdf-extractor.tar
```

#### Step 2: Run the Container

```bash
docker run -d -p 8000:8000 --name dnit-pdf-extractor dnit-pdf-extractor:latest
```

#### Step 3: Access the Application

Open your web browser and navigate to:
```
http://localhost:8000
```

#### Managing the Container

**Stop the container:**
```bash
docker stop dnit-pdf-extractor
```

**Start the container again:**
```bash
docker start dnit-pdf-extractor
```

**Remove the container:**
```bash
docker stop dnit-pdf-extractor
docker rm dnit-pdf-extractor
```

**View logs:**
```bash
docker logs dnit-pdf-extractor
```

**View real-time logs:**
```bash
docker logs -f dnit-pdf-extractor
```

---

### Option 2: Building from Source (For Developers)

If you have the source code, you can build and run using Docker Compose:

#### Step 1: Navigate to Project Directory

```bash
cd dnit-pdf-extractor
```

#### Step 2: Build and Start

```bash
docker compose up -d --build
```

#### Step 3: Access the Application

Open your web browser and navigate to:
```
http://localhost:8000
```

#### Managing with Docker Compose

**View status:**
```bash
docker compose ps
```

**Stop the application:**
```bash
docker compose down
```

**View logs:**
```bash
docker compose logs
```

**View real-time logs:**
```bash
docker compose logs -f
```

**Rebuild after code changes:**
```bash
docker compose up -d --build
```

---

## Troubleshooting

### Port Already in Use

If port 8000 is already in use, you can map to a different port:

**Using docker run:**
```bash
docker run -d -p 8080:8000 --name dnit-pdf-extractor dnit-pdf-extractor:latest
```
Then access at: `http://localhost:8080`

**Using docker-compose.yml:**
Edit the `ports` section in `docker-compose.yml`:
```yaml
ports:
  - "8080:8000"
```

### Check if Container is Running

```bash
docker ps
```

### Container Exits Immediately

Check the logs for errors:
```bash
docker logs dnit-pdf-extractor
```

### Cannot Connect to Application

1. Verify the container is running: `docker ps`
2. Check logs: `docker logs dnit-pdf-extractor`
3. Ensure no firewall is blocking port 8000
4. Try accessing `http://127.0.0.1:8000` instead of `localhost`

### Memory Issues

EasyOCR requires significant memory. Ensure Docker has at least 4GB RAM allocated:

- **Docker Desktop**: Settings → Resources → Memory (set to at least 4GB)

---

## Using the Application

1. Open `http://localhost:8000` in your browser
2. Click or drag-and-drop DNIT PDF files to upload
3. The application will process the PDFs and download an Excel file
4. The Excel file contains all extracted data with a `Source_File` column indicating which PDF each row came from

---

## Uninstalling

### Remove Container and Image

```bash
# Stop and remove container
docker stop dnit-pdf-extractor
docker rm dnit-pdf-extractor

# Remove image
docker rmi dnit-pdf-extractor:latest
```

### Using Docker Compose

```bash
# Stop and remove containers
docker compose down

# Remove images
docker compose down --rmi all
```

---

## System Requirements

- **CPU**: Multi-core recommended (OCR is CPU-intensive)
- **RAM**: Minimum 4GB, 8GB recommended
- **Disk**: ~2GB for Docker image
- **OS**: Windows 10/11, macOS 10.15+, or modern Linux distribution

---

## Support

For issues or questions, contact the development team or check the project repository.
