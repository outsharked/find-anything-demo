FROM ubuntu:24.04

ARG RELEASE_VERSION=0.7.3

RUN apt-get update && apt-get install -y \
    ca-certificates curl python3 \
    && rm -rf /var/lib/apt/lists/*

# Download and unpack find-anything release binaries
RUN curl -fsSL \
    "https://github.com/outsharked/find-anything/releases/download/v${RELEASE_VERSION}/find-anything-v${RELEASE_VERSION}-linux-x86_64.tar.gz" \
    | tar -xz -C /usr/local/bin --strip-components=1

# Pre-seeded content — copied from the repo, no runtime download needed
COPY content/ /content/

COPY scripts/ /scripts/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8765
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
