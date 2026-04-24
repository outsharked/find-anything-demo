FROM ubuntu:24.04

ARG RELEASE_VERSION=0.7.5

RUN apt-get update && apt-get install -y \
    ca-certificates curl python3 python3-lxml \
    && rm -rf /var/lib/apt/lists/*

# Download and unpack find-anything release binaries
RUN curl -fsSL \
    "https://github.com/outsharked/find-anything/releases/download/v${RELEASE_VERSION}/find-anything-v${RELEASE_VERSION}-linux-x86_64.tar.gz" \
    | tar -xz -C /usr/local/bin --strip-components=1

# Pre-seeded content — injected at build time via --build-context content=...
COPY --from=content . /content/

# Demo information — maintained in this repo
COPY content/demo/ /content/demo/

COPY scripts/ /scripts/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8765
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
