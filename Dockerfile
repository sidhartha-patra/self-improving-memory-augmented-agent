FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY docs ./docs
COPY evals ./evals

RUN pip install --upgrade pip && pip install .

EXPOSE 8000

CMD ["python", "-m", "self_improving_memory_augmented_agent", "serve", "--host", "0.0.0.0", "--port", "8000"]

