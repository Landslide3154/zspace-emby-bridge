# 国内网络可用 --build-arg BASE=... / PIP_INDEX=... 走镜像站
#   docker build --build-arg BASE=docker.1ms.run/library/python:3.12-slim \
#                --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple -t zspace-emby-bridge:local .
ARG BASE=python:3.12-slim
FROM ${BASE}

ARG PIP_INDEX=https://pypi.org/simple

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    LISTEN_PORT=8022

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir --index-url ${PIP_INDEX} .

RUN mkdir -p /data

EXPOSE 8022

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import os,urllib.request,sys; port=os.environ.get('LISTEN_PORT','8022'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=3).status==200 else 1)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${LISTEN_PORT:-8022}"]
