FROM python:3.13-slim
WORKDIR /app
COPY gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home pillbox && mkdir /data && chown pillbox:pillbox /data
COPY gateway /app/gateway
USER pillbox
EXPOSE 5000
CMD ["waitress-serve", "--listen=0.0.0.0:5000", "--call", "gateway.app:create_app"]
