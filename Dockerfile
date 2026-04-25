FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 5005

CMD ["gunicorn", "-b", "0.0.0.0:5005", "jellyswipe:app"]
