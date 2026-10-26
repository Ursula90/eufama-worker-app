FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/media

EXPOSE 8765

ENV DATABASE_URL=sqlite:////data/eufama.db
ENV MEDIA_DIR=/data/media

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
