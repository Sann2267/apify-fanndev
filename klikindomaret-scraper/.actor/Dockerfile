# Klikindomaret actor image: Python (curl_cffi + Camoufox) + Node (jsdom AWS-WAF
# token minter). Camoufox needs a real Firefox runtime; Node runs the headless
# challenge solver.
FROM apify/actor-python:3.12

# --- Node.js (for the jsdom AWS-WAF token minter) -----------------------------
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# --- Python deps --------------------------------------------------------------
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Camoufox browser + system libs it needs to run headless ------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgtk-3-0 libx11-xcb1 libasound2 libdbus-glib-1-2 libxtst6 \
        libxrandr2 libxcomposite1 libxdamage1 libxfixes3 libxcursor1 \
        libgbm1 libpango-1.0-0 libcairo2 libatk1.0-0 libatk-bridge2.0-0 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && python -m camoufox fetch

# --- Node deps (jsdom) --------------------------------------------------------
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

COPY . ./

CMD ["python", "-m", "src"]
