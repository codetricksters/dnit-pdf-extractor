# Estágio 1: o build do frontend React. Só frontend/dist vai para a imagem
# final; Node não é dependência de execução.
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# System dependencies:
#   gcc, libgl1, libglib2.0-0 -> pdfplumber / easyocr
#   tesseract-ocr (+ Portuguese data) -> the primary OCR engine; without it the
#     container silently falls back to EasyOCR
#   postgresql-client-16 -> pg_dump / pg_restore used by the backup feature
RUN apt-get update && apt-get install -y \
    gcc \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-por \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# The client major must match the server (postgres:16 in docker-compose.yml):
# pg_dump emits directives from its own version, so a newer client produces a
# dump that the server refuses to restore. Debian's own postgresql-client tracks
# the distribution's version, hence the PGDG repository to pin 16.
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] \
http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# O SPA construído no estágio 1 (app/spa.py serve frontend/dist).
COPY --from=frontend /frontend/dist ./frontend/dist

# Create tmp directory for uploads
RUN mkdir -p tmp

# Expose port 8000
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
