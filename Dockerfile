# Latest stable Debian-based Python image
FROM python:3.11-slim-bookworm

# System dependencies (Git aur zaroori tools)
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Work directory set karna
WORKDIR /app

# Requirements install karna
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Bot code copy karna
COPY . .

# Bot run karne ki command
CMD ["python3", "bot.py"]
