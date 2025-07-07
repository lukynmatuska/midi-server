FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y \
    libasound2-dev \
    git \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Create midiuser user
ARG USERNAME=midiuser
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update && apt-get install -y sudo \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/nopasswd \
    && chmod 0440 /etc/sudoers.d/nopasswd

# Set working directory
WORKDIR /app

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the code
COPY . .

# Fix permissions
RUN usermod -aG audio midiuser

# Use non-root user
USER midiuser

# Use PORT env var with fallback
ENV PORT=8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
