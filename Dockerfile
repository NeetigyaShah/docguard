# DocGuard GitHub Action image.
FROM python:3.11-slim

# git is required to compute diffs inside the runner workspace
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /action
COPY pyproject.toml ./
COPY src ./src
# github extra = PyGithub (comments/PRs); openai/anthropic for real LLM when configured
RUN pip install --no-cache-dir ".[github,openai,anthropic]"

COPY scripts/action_entrypoint.sh /action/entrypoint.sh
RUN chmod +x /action/entrypoint.sh

ENTRYPOINT ["/action/entrypoint.sh"]
