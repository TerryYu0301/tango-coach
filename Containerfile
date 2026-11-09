# Tango Coach 的容器設定檔（Podman 和 Docker 都能用）
FROM python:3.11-slim

# 讓 print 立刻顯示，並確保中文、日文不會變成亂碼
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8

WORKDIR /app

# 先裝套件（requirements.txt 沒變時，重新 build 會直接用快取，比較快）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再複製程式碼和單字表
COPY src/ src/
COPY data/*.csv data/

# API 金鑰不放進映像檔，執行時用 --env-file .env 傳進來
CMD ["python", "-m", "src.main"]