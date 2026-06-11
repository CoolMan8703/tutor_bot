FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python3", "-c", "import os, uvicorn; uvicorn.run('api.main:app', host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))"]
