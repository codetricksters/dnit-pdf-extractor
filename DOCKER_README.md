# Docker Distribution Package

This package contains everything needed to run the DNIT PDF Extractor application in Docker.

## Quick Start for Recipients

1. **Install Docker Desktop** (if not already installed)
   - Download from: https://www.docker.com/products/docker-desktop

2. **Load the Docker Image**
   ```bash
   docker load -i dnit-pdf-extractor.tar
   ```

3. **Run the Application**
   ```bash
   docker run -d -p 8000:8000 --name dnit-pdf-extractor dnit-pdf-extractor:latest
   ```

4. **Access the Application**
   - Open your browser and go to: http://localhost:8000
   - Upload DNIT PDF files and download the extracted Excel

5. **Stop the Application**
   ```bash
   docker stop dnit-pdf-extractor
   ```

For complete instructions, see **DOCKER_INSTRUCTIONS.md**

---

## For the Project Maintainer

### Creating the Distribution Package

1. **Build the Docker image:**
   ```bash
   docker compose up -d --build
   ```

2. **Test the application:**
   ```bash
   # Check it's running
   docker compose ps
   
   # View logs
   docker compose logs
   
   # Test in browser
   open http://localhost:8000
   ```

3. **Export the image:**
   ```bash
   ./export-image.sh
   ```

4. **Distribute:**
   - Send the `dnit-pdf-extractor.tar` file (will be ~2GB)
   - Include `DOCKER_INSTRUCTIONS.md` for recipients
   - File can be shared via cloud storage, USB drive, etc.

### Files in This Package

- `Dockerfile` - Image build instructions
- `docker-compose.yml` - Orchestration config (optional for end users)
- `requirements.txt` - Python dependencies
- `.dockerignore` - Files excluded from image
- `export-image.sh` - Script to export image to .tar
- `DOCKER_INSTRUCTIONS.md` - Complete user guide
- `DOCKER_README.md` - This file

### Image Details

- **Base Image:** python:3.12-slim
- **Exposed Port:** 8000
- **Environment:** Production mode
- **Dependencies:** FastAPI, pdfplumber, pandas, openpyxl, easyocr, dash
- **System Packages:** gcc, libgl1, libglib2.0-0

### Troubleshooting Build Issues

**Out of space:**
```bash
docker system prune -a
```

**Build cache issues:**
```bash
docker compose build --no-cache
```

**View detailed build logs:**
```bash
docker compose up --build
```

### Alternative: Docker Hub Distribution

Instead of distributing a .tar file, you can push to Docker Hub:

```bash
# Tag the image
docker tag dnit-pdf-extractor:latest username/dnit-pdf-extractor:latest

# Push to Docker Hub
docker push username/dnit-pdf-extractor:latest
```

Then recipients can simply:
```bash
docker pull username/dnit-pdf-extractor:latest
docker run -d -p 8000:8000 --name dnit-pdf-extractor username/dnit-pdf-extractor:latest
```

---

## Testing Checklist Before Distribution

- [ ] Image builds successfully
- [ ] Container starts without errors
- [ ] Application accessible at http://localhost:8000
- [ ] Can upload and process sample PDFs
- [ ] Excel download works correctly
- [ ] OCR functionality works (for scanned PDFs)
- [ ] Dashboard accessible at http://localhost:8000/dash/
- [ ] Container restarts properly (`docker restart`)
- [ ] Logs show no errors (`docker logs`)
- [ ] Export script creates valid .tar file
- [ ] Load from .tar file works on clean system

---

## Size Optimization Tips

The image is large (~2GB) due to EasyOCR dependencies. To reduce size:

1. **Use multi-stage builds** (not implemented yet)
2. **Remove unnecessary model files** after EasyOCR install
3. **Use alpine base** (requires more system dependencies)
4. **Compress the .tar file:**
   ```bash
   gzip dnit-pdf-extractor.tar
   # Creates dnit-pdf-extractor.tar.gz (~1GB)
   ```

Recipients would then:
```bash
gunzip dnit-pdf-extractor.tar.gz
docker load -i dnit-pdf-extractor.tar
```
