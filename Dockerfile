FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY . .

# Ensure start script is executable
RUN chmod +x start.sh

# By default, Cloud Run sets PORT=8080
ENV PORT=8080

CMD ["./start.sh"]
