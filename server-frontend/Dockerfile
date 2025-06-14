FROM python:3.11-slim

WORKDIR /app

COPY server-frontend/ ./server-frontend
COPY server-frontend/.streamlit /app/.streamlit
COPY shared/ ./shared/symbols_intervals.py

RUN pip install --no-cache-dir -r server-frontend/requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "server-frontend/Main.py", "--server.port=8501", "--server.address=0.0.0.0", "--browser.gatherUsageStats", "false"]
