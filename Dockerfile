FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 app \
    && mkdir /data && chown app /data
COPY *.py .
ENV DATA_DIR=/data FASTMCP_HOME=/data/fastmcp PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER app
CMD ["python", "server.py"]
