# 1. Base image (Java + Linux)
FROM eclipse-temurin:17-jdk-jammy

# 2. System dependencies
RUN apt-get update && \
    apt-get install -y \
        python3 python3-pip \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        libjpeg8-dev zlib1g-dev libpng-dev \
        ghostscript \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 3. Workdir
WORKDIR /app

# 4. Python deps
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. App code
COPY . .

# 6. Optional sanity checks
RUN echo "Checking services:" && ls -la /app/services || true
RUN echo "Checking PPT converter:" && ls -la /app/ppt_converter/target || true

# 7. Cloud Run port
ENV PORT=8080
EXPOSE 8080

# 8. Start FastAPI
CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
