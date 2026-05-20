FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/wallet_service ./services/wallet_service
ENV PYTHONPATH=/app
CMD ["uvicorn", "services.wallet_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
