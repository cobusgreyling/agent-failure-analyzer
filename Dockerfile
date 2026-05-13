FROM python:3.12-slim

LABEL maintainer="Cobus Greyling <greyling.cobus@gmail.com>"
LABEL description="Agent Failure Analyzer — classify AI agent session failures"

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY agent_failure_analyzer/ ./agent_failure_analyzer/

RUN pip install --no-cache-dir '.[dashboard]'

ENTRYPOINT ["afa"]
CMD ["--help"]
