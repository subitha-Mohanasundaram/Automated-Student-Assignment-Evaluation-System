FROM debian:bookworm-slim
WORKDIR /workspace
RUN apt-get update && apt-get install -y --no-install-recommends g++ gcc libc6-dev make && rm -rf /var/lib/apt/lists/*
RUN g++ --version

