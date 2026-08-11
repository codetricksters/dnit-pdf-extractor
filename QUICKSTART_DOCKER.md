# Quick Start Guide - Docker Distribution

## For the Person Receiving This Package

### What You Need
1. **Docker Desktop** installed on your computer
   - Windows/Mac: [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
   - Follow the installer instructions and restart your computer if prompted

2. **The File:** `dnit-pdf-extractor.tar` (approximately 2GB)

### Installation (3 Simple Steps)

#### Step 1: Open Terminal/Command Prompt

**Windows:**
- Press `Win + R`, type `cmd`, press Enter

**Mac:**
- Press `Cmd + Space`, type `terminal`, press Enter

**Linux:**
- Press `Ctrl + Alt + T`

#### Step 2: Load the Image

Navigate to the folder containing the `.tar` file and run:

```bash
docker load -i dnit-pdf-extractor.tar
```

Wait for it to complete (shows "Loaded image: dnit-pdf-extractor:latest")

#### Step 3: Start the Application

```bash
docker run -d -p 8000:8000 --name dnit-pdf-extractor dnit-pdf-extractor:latest
```

### Using the Application

1. Open your web browser
2. Go to: **http://localhost:8000**
3. Drag and drop your DNIT PDF files or click to upload
4. The application will process them and download an Excel file

### Managing the Application

#### To Stop
```bash
docker stop dnit-pdf-extractor
```

#### To Start Again
```bash
docker start dnit-pdf-extractor
```

#### To Remove Completely
```bash
docker stop dnit-pdf-extractor
docker rm dnit-pdf-extractor
docker rmi dnit-pdf-extractor:latest
```

---

## For the Person Sending This Package

### How to Create the Distribution Package

#### 1. Build the Docker Image

```bash
cd dnit-pdf-extractor
docker compose up -d --build
```

Wait 5-15 minutes for the build to complete.

#### 2. Test the Application

```bash
./test-docker.sh
```

Or manually:
- Open http://localhost:8000
- Upload a sample PDF
- Verify Excel download works

#### 3. Export the Image

```bash
./export-image.sh
```

This creates `dnit-pdf-extractor.tar` (~2GB)

#### 4. Share the Package

Send these files to your recipient:
- `dnit-pdf-extractor.tar` (the Docker image)
- `DOCKER_INSTRUCTIONS.md` (detailed guide)
- `QUICKSTART_DOCKER.md` (this file)

**Transfer Methods:**
- USB drive
- Cloud storage (Google Drive, Dropbox, etc.)
- Internal file share
- WeTransfer (if under their size limit)

**Optional:** Compress the .tar file to save space:
```bash
gzip dnit-pdf-extractor.tar
# Creates dnit-pdf-extractor.tar.gz (~1GB)
```

Recipient would then run:
```bash
gunzip dnit-pdf-extractor.tar.gz
docker load -i dnit-pdf-extractor.tar
```

---

## Troubleshooting

### "Port 8000 is already in use"

Use a different port:
```bash
docker run -d -p 8080:8000 --name dnit-pdf-extractor dnit-pdf-extractor:latest
```
Then access: http://localhost:8080

### "Cannot connect to Docker daemon"

Make sure Docker Desktop is running:
- **Windows/Mac:** Look for Docker icon in system tray, click to start
- **Linux:** Run `sudo systemctl start docker`

### "Container exits immediately"

Check the logs:
```bash
docker logs dnit-pdf-extractor
```

### Application is slow or crashes

Docker needs more memory:
1. Open Docker Desktop
2. Go to Settings → Resources → Memory
3. Set to at least 4GB (8GB recommended)
4. Click "Apply & Restart"

---

## What This Application Does

DNIT PDF Extractor processes "Resumo da Medição" PDF files from DNIT and extracts tabular data into Excel format. It supports:

- ✅ Multiple PDF upload at once
- ✅ Text-based PDFs (native digital PDFs)
- ✅ Scanned PDFs (OCR processing)
- ✅ Automatic data cleaning and formatting
- ✅ Source file tracking
- ✅ Dashboard for viewing processed jobs

---

## System Requirements

- **Operating System:** Windows 10/11, macOS 10.15+, or modern Linux
- **RAM:** 4GB minimum, 8GB recommended
- **Disk Space:** 2GB for Docker image
- **CPU:** Multi-core processor recommended
- **Docker Desktop:** Latest version

---

## Need Help?

See `DOCKER_INSTRUCTIONS.md` for:
- Detailed installation steps
- Advanced configuration
- Complete troubleshooting guide
- Uninstallation instructions

---

## Quick Command Reference

```bash
# Load image
docker load -i dnit-pdf-extractor.tar

# Start
docker run -d -p 8000:8000 --name dnit-pdf-extractor dnit-pdf-extractor:latest

# Stop
docker stop dnit-pdf-extractor

# Start again
docker start dnit-pdf-extractor

# View logs
docker logs dnit-pdf-extractor

# View logs in real-time
docker logs -f dnit-pdf-extractor

# Check status
docker ps

# Remove
docker rm -f dnit-pdf-extractor

# Remove image
docker rmi dnit-pdf-extractor:latest
```

---

**That's it!** The application should now be running at http://localhost:8000
