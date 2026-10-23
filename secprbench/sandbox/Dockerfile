FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git curl ripgrep ca-certificates iptables nodejs npm && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 1000 --create-home reviewer
COPY claude /usr/local/bin/claude
RUN chmod 755 /usr/local/bin/claude
ARG CODEX_VERSION=0.149.1
RUN npm install -g @openai/codex@${CODEX_VERSION}
COPY package /opt/secprbench
RUN pip install --no-cache-dir -r /opt/secprbench/requirements.lock /opt/secprbench
ENV SECPRBENCH_CONFIG_DIR=/opt/secprbench/configs HOME=/home/reviewer PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
USER reviewer
ENTRYPOINT ["python", "-I", "-m", "secprbench.sandbox.entrypoint"]
