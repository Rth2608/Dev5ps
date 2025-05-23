FROM python:3.11-slim

WORKDIR /app

COPY server-collect_data/ ./server-collect_data
COPY shared/ ./shared/
COPY .env .env

RUN pip install --no-cache-dir -r server-collect_data/requirements.txt

ENV PYTHONPATH=/server-collect_data

CMD ["python", "server-collect_data/fetcher/main_fetch.py"]