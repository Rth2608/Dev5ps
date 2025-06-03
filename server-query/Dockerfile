FROM python:3.11-slim

WORKDIR /app

COPY server-query/ ./server-query
COPY shared/ ./shared/
COPY .env .env

RUN pip install --no-cache-dir -r server-query/requirements.txt

EXPOSE 8082

CMD ["uvicorn", "server-query.main_query:app", "--host", "0.0.0.0", "--port", "8082"]