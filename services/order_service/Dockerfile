FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir fastapi uvicorn requests
ENV PYTHONPATH=/app
CMD ["uvicorn", "services.order_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
