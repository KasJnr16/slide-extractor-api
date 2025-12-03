# Use Temurin 17 JDK as base
FROM eclipse-temurin:17-jdk-jammy

# Install Python 3 and pip
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# Make sure the jar exists
RUN ls -l /app/ppt_converter/target/

EXPOSE 5000
ENV PORT=5000

CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
