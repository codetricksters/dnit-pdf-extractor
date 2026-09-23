# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# System dependencies:
#   gcc, libgl1, libglib2.0-0 -> pdfplumber / easyocr
#   tesseract-ocr (+ Portuguese data) -> the primary OCR engine; without it the
#     container silently falls back to EasyOCR
#   postgresql-client -> pg_dump / pg_restore used by the backup feature
RUN apt-get update && apt-get install -y \
    gcc \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-por \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create tmp directory for uploads
RUN mkdir -p tmp

# Expose port 8000
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
