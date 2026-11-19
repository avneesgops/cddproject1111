FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
COPY verifynews/ ./verifynews/
COPY assets/ ./assets/
COPY datasets/xfact_claims.csv datasets/XFACT-ATTRIBUTION.md ./datasets/
COPY datasets/verification/ ./datasets/verification/
COPY datasets/averitec/ATTRIBUTION.md ./datasets/averitec/ATTRIBUTION.md
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
