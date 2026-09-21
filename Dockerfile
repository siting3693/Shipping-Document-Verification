FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY . .

# Ensure start script is normalized and executable
RUN sed -i 's/\r$//' /app/start.sh && \
    chmod +x /app/start.sh

# By default, Cloud Run sets PORT=8080
ENV PORT=8080

ENTRYPOINT ["/app/start.sh"]
