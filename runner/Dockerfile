FROM ghcr.io/actions/actions-runner:latest

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends jq \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /home/runner/entrypoint.sh
RUN chmod +x /home/runner/entrypoint.sh && chown runner:runner /home/runner/entrypoint.sh

USER runner

ENTRYPOINT ["/home/runner/entrypoint.sh"]
