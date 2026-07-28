FROM debian:bookworm-slim

ARG GOOGLE_CHROME_VERSION

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        xvfb \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
        | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && chrome_package="google-chrome-stable" \
    && if [ -n "${GOOGLE_CHROME_VERSION}" ]; then \
        chrome_package="${chrome_package}=${GOOGLE_CHROME_VERSION}"; \
       fi \
    && apt-get install -y --no-install-recommends \
        "${chrome_package}" \
    && apt-mark hold google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system chrome \
    && useradd --system --gid chrome --home-dir /var/lib/chrome chrome \
    && install -d -o chrome -g chrome -m 0700 /var/lib/chrome/profile

COPY --chmod=0755 entrypoint.sh check-cdp.sh /usr/local/bin/

USER chrome

EXPOSE 9222

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
