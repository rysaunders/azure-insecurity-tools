FROM python:3.12-alpine

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# App Service probes this port (set WEBSITES_PORT=80 too)
ENV PORT=80
EXPOSE 80

# Gunicorn keeps one worker simple; logs to stdout/stderr
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} -w 1 app:app --access-logfile - --error-logfile -"]
