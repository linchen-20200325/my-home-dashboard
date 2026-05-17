# 房產攻略 — Streamlit App Docker image
# 用法：
#   docker build -t real-estate-app .
#   docker run -p 8501:8501 -e OPENAI_API_KEY=sk-... real-estate-app
#
# 設計：
#   - python:3.11-slim 對齊 Streamlit Cloud / CI Python 版本
#   - 依賴層獨立 COPY 以利 Docker layer cache
#   - 非 root 使用者執行（最小權限）
#   - HEALTHCHECK 配合 orchestrator (k8s / docker swarm) 自動恢復

FROM python:3.11-slim

# 安全 / 維運 metadata
LABEL org.opencontainers.image.source="https://github.com/CornCorn-2015/my-house-2026"
LABEL org.opencontainers.image.description="14 模組房產投資攻略 Streamlit App"

# 系統依賴最小化（plotly / streamlit 不需要編譯 C extension）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1️⃣ 先 COPY requirements 利用 Docker layer cache：
#    只要 requirements.txt 沒變動，pip install 就不重跑。
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 2️⃣ 再 COPY 應用程式碼
COPY main.py streamlit_app.py app.py ./
COPY app/ ./app/
# 三個入口檔同步 COPY（streamlit_app.py 是 Streamlit Cloud 預設偵測檔名）

# 3️⃣ 建立非 root 使用者並切換
RUN useradd --create-home --shell /bin/bash streamlit \
    && chown -R streamlit:streamlit /app
USER streamlit

EXPOSE 8501

# 健康檢查：每 30 秒戳 /_stcore/health
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health').read()" || exit 1

# 預設用 streamlit_app.py 作為入口（與 Streamlit Cloud 預設偵測一致）
CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
