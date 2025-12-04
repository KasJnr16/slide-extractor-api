# 1. Base image (JDK + Ubuntu Jammy)
FROM eclipse-temurin:17-jdk-jammy

# 2. Install system dependencies
RUN apt-get update && \
    apt-get install -y \
        python3 python3-pip python3-venv \
        tesseract-ocr \
        poppler-utils \
        libjpeg8-dev zlib1g-dev libpng-dev \
        ghostscript \
        && rm -rf /var/lib/apt/lists/*

# 3. Workdir
WORKDIR /app

# 4. Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. Copy project files
COPY . .

# 6. Verify JAR exists (Debug only)
RUN echo "Checking Java converter JAR:" && ls -l /app/ppt_converter/target/

# 7. Expose port
EXPOSE 5000
ENV PORT=5000

# 8. Start server
CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
