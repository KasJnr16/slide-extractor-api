# 1. Base image (JDK + Ubuntu Jammy)
FROM eclipse-temurin:17-jdk-jammy

# 2. Install system dependencies
RUN apt-get update && \
    apt-get install -y \
        python3 python3-pip python3-venv \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        libjpeg8-dev zlib1g-dev libpng-dev \
        ghostscript \
        && rm -rf /var/lib/apt/lists/*

# 3. Workdir
WORKDIR /app

# 4. Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. Copy project files (including services package)
COPY . .

# 6. Verify JAR exists (for PPT converter)
RUN echo "Checking Java converter JAR:" && ls -l /app/ppt_converter/target/ || echo "JAR not found - PPT conversion may not work"

# 7. Verify services package structure
RUN echo "Checking services package:" && ls -la /app/services/

# 8. Create necessary directories
RUN mkdir -p /app/uploads /app/temp

# 9. Expose port
EXPOSE 5000
ENV PORT=5000

# 10. Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# 11. Start server
CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
