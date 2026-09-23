# Optional: deploy on Railway/Render with Docker for predictable Python+Node builds
FROM node:20-bookworm-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json* ./
COPY scripts ./scripts

RUN pip3 install --break-system-packages requests \
  && python3 scripts/fetch_and_patch.py \
  && npm install --omit=dev

COPY server.js ./

ENV NODE_ENV=production
ENV HOST=0.0.0.0
EXPOSE 3000

CMD ["npm", "start"]
