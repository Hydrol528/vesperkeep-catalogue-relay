FROM python:3.12-slim
WORKDIR /app
COPY shared_catalogue.py shared_catalogue_http.py ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65534:65534
CMD ["python", "shared_catalogue_http.py"]
