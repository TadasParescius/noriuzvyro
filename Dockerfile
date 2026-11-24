FROM python:3.12-slim
WORKDIR /app
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY app ./app
COPY scripts ./scripts
COPY database ./database
COPY main.py .
RUN useradd --create-home web
USER web
ENV HOST=0.0.0.0 PORT=3000 PYTHONDONTWRITEBYTECODE=1
EXPOSE 3000
CMD ["sh", "-c", "python -m scripts.setup_db && python main.py"]
