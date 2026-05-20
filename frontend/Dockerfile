FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY frontend ./frontend
WORKDIR /app/frontend
CMD ["python", "app.py"]
