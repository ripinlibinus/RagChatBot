# Gunakan Python base image yang ringan
FROM python:3.11-slim

# Set environment (opsional tapi bagus)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies (kalau perlu build wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Set working directory di dalam container
WORKDIR /app

# Copy file requirements dan install dependency
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh source code ke dalam container
COPY . .

# (Opsional) Kalau ada directory khusus yang tidak perlu di-copy, pakai .dockerignore

# Expose port aplikasi (misal 8000)
EXPOSE 8000

# Command untuk menjalankan app
# SESUAIKAN dengan struktur project-mu
# Contoh FastAPI:
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

# Kalau app-mu ada di main.py, ubah jadi:
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Kalau ada package misal src/app/main.py -> app = FastAPI():
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
