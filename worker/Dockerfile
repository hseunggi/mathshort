FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

# ffmpeg 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    fonts-nanum \
    fontconfig \
 && fc-cache -f -v \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
