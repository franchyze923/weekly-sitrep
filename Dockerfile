FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /data && useradd -M -u 10001 sitrep && chown sitrep /data
USER sitrep
# podman build --build-arg APP_BUILD=$(git rev-parse --short HEAD) ...
ARG APP_BUILD=""
ENV DATABASE_URL=sqlite:////data/sitrep.db APP_BUILD=$APP_BUILD
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
