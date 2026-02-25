FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run sets PORT automatically, default to 8000
ENV PORT=8000
EXPOSE 8000

# Run the backend using uvicorn, binding to $PORT
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]