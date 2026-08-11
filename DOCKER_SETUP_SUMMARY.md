# Docker Setup Summary

## What Was Done

### 1. Docker Configuration Files Created

#### `Dockerfile`
- Base image: `python:3.12-slim`
- System dependencies: `gcc`, `libgl1`, `libglib2.0-0` (required for EasyOCR/OpenCV)
- Python dependencies installed from `requirements.txt`
- Exposes port 8000
- Working directory: `/app`

#### `docker-compose.yml`
- Service name: `dnit-pdf-extractor`
- Port mapping: `8000:8000`
- Environment: `APP_ENV=production`
- Optional volume mount for `tmp/` directory
- Auto-restart policy: `unless-stopped`

#### `.dockerignore`
- Excludes development files, caches, and unnecessary content
- Reduces image size and build time
- Prevents sensitive files from being included

### 2. Dependencies Updated

#### `requirements.txt`
All project dependencies with minimum versions:
- fastapi >= 0.137.1
- uvicorn[standard] >= 0.34.0
- pdfplumber >= 0.11.10
- pandas >= 2.2.0
- openpyxl >= 3.1.5
- python-multipart >= 0.0.20
- jinja2 >= 3.1.6
- aiofiles >= 25.1.0
- python-dotenv >= 1.2.2
- easyocr >= 1.7.2
- aiosqlite >= 0.20.0
- dash >= 4.3.0
- dash-bootstrap-components >= 2.0.4
- a2wsgi >= 1.10.10

### 3. Scripts Created

#### `export-image.sh`
- Exports Docker image to a portable `.tar` file
- Includes validation checks
- Shows file size and distribution instructions
- Makes the image shareable without Docker Hub

#### `test-docker.sh`
- Automated testing script
- Checks if container is running
- Verifies application responds correctly
- Scans logs for errors
- Confirms homepage is accessible

### 4. Documentation Created

#### `DOCKER_INSTRUCTIONS.md`
Complete user guide covering:
- Prerequisites and installation
- Two installation options (from .tar or from source)
- Container management commands
- Troubleshooting common issues
- Port conflicts and configuration
- System requirements
- Uninstallation steps

#### `DOCKER_README.md`
Maintainer guide covering:
- Quick start for recipients
- How to create distribution package
- Testing checklist
- File descriptions
- Alternative distribution methods (Docker Hub)
- Size optimization tips

#### `DOCKER_SETUP_SUMMARY.md` (this file)
- Overview of all changes
- Build and test procedures
- Known issues and notes

---

## How to Build and Test

### Building the Image

```bash
# Clean build (recommended after requirement changes)
docker compose build --no-cache

# Regular build (uses cache)
docker compose build
```

**Expected build time:** 5-15 minutes (depends on internet speed and CPU)
**Final image size:** ~2GB (EasyOCR + PyTorch + dependencies)

### Running the Container

```bash
# Start in detached mode
docker compose up -d

# Start with logs visible
docker compose up

# View logs of running container
docker compose logs -f
```

### Testing

```bash
# Automated test
./test-docker.sh

# Manual test
curl http://localhost:8000
# Should return HTML page

# Open in browser
open http://localhost:8000
```

### Exporting for Distribution

```bash
# Export image to .tar file
./export-image.sh

# Result: dnit-pdf-extractor.tar (~2GB)
```

---

## For Recipients

### Quick Install

1. Install Docker Desktop
2. Load image: `docker load -i dnit-pdf-extractor.tar`
3. Run: `docker run -d -p 8000:8000 --name dnit-pdf-extractor dnit-pdf-extractor:latest`
4. Access: http://localhost:8000

Full instructions in `DOCKER_INSTRUCTIONS.md`

---

## Known Issues and Notes

### Build Time
- First build takes 5-15 minutes due to large ML dependencies (PyTorch, EasyOCR)
- Subsequent builds are faster with Docker cache
- Use `--no-cache` flag after changing requirements.txt

### Image Size
- Final image is ~2GB
- Most space used by PyTorch and EasyOCR models
- Can be compressed to ~1GB with gzip for distribution
- Alternative: use Docker Hub instead of .tar files

### System Requirements
- **Memory:** Minimum 4GB RAM, 8GB recommended
  - EasyOCR is memory-intensive during OCR operations
  - Configure in Docker Desktop: Settings → Resources → Memory
- **CPU:** Multi-core recommended for OCR performance
- **Disk:** ~2GB for image, plus space for temporary files

### OCR Functionality
- EasyOCR downloads language models on first use
- Models are cached inside the container
- First OCR operation may take longer
- Supports Portuguese (pt) and English (en) by default

### Port Configuration
- Default: port 8000
- Change in `docker-compose.yml` if needed
- Or use: `docker run -p 8080:8000 ...` for different host port

### Persistence
- No volumes mounted by default (stateless)
- Database (SQLite) stored inside container
- Data lost when container is removed
- To persist: add volume mount in docker-compose.yml

### Development vs Production
- This setup is for **production** deployment
- For development, use: `uv run uvicorn main:app --reload`
- Development includes hot-reload and debug features

---

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker compose logs

# Common issues:
# - Port 8000 already in use
# - Insufficient memory
# - Import errors (rebuild with --no-cache)
```

### Application Not Responding
```bash
# Check container is running
docker compose ps

# Verify port
curl http://localhost:8000

# Check firewall/antivirus isn't blocking
```

### Build Fails
```bash
# Clean everything and rebuild
docker compose down
docker system prune -a  # Warning: removes all unused images
docker compose build --no-cache

# Check disk space
df -h
```

### Out of Memory
```bash
# Increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory → 8GB

# Or reduce concurrent workers in app
# Edit Dockerfile CMD line
```

---

## Maintenance

### Updating the Application

1. Update code
2. Rebuild image: `docker compose build`
3. Restart: `docker compose up -d`

### Cleaning Old Images

```bash
# Remove old images
docker image prune -a

# Remove everything (careful!)
docker system prune -a
```

### Viewing Resource Usage

```bash
# CPU and memory usage
docker stats dnit-pdf-extractor-dnit-pdf-extractor-1

# Disk usage
docker system df
```

---

## Distribution Checklist

Before sending to others:

- [ ] Build completes successfully
- [ ] Container starts without errors
- [ ] Application accessible at http://localhost:8000
- [ ] Upload functionality works
- [ ] Excel download works
- [ ] OCR processing works (test with scanned PDF)
- [ ] Dashboard accessible at /dash/
- [ ] Export creates valid .tar file
- [ ] Test loading .tar on different machine (if possible)
- [ ] Include DOCKER_INSTRUCTIONS.md with .tar file
- [ ] Verify system requirements documented
- [ ] Include sample PDFs for testing (optional)

---

## Support Information

### For End Users
- See `DOCKER_INSTRUCTIONS.md` for installation and usage
- Check Docker Desktop is running
- Ensure port 8000 is available
- Verify minimum 4GB RAM allocated to Docker

### For Maintainers
- Source code: Check repository for latest version
- Requirements: Keep `requirements.txt` and `pyproject.toml` in sync
- Testing: Use `test-docker.sh` before distribution
- Size: Consider gzip compression for large .tar files

### Common Commands Reference

```bash
# Build
docker compose build
docker compose build --no-cache

# Run
docker compose up -d
docker compose up

# Stop
docker compose down
docker compose stop

# Logs
docker compose logs
docker compose logs -f

# Status
docker compose ps
docker stats

# Export
./export-image.sh

# Test
./test-docker.sh
```

---

## Next Steps

1. **Wait for build to complete** (currently running in background)
2. **Test the application** with `./test-docker.sh`
3. **Export the image** with `./export-image.sh`
4. **Test on clean system** (optional but recommended)
5. **Distribute** `.tar` file with `DOCKER_INSTRUCTIONS.md`

---

**Build Status:** Check with `docker compose ps` or `docker compose logs`
