FROM python:3.11

ENV PYTHONUNBUFFERED 1

WORKDIR /fastapi

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000