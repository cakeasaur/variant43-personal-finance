FROM python:3.12-slim

WORKDIR /app

# Minimal tooling container for CI-like checks (no GUI).
COPY requirements/dev.txt /app/requirements/dev.txt
COPY requirements/ci.txt /app/requirements/ci.txt
COPY pyproject.toml /app/pyproject.toml

# ci.txt — headless subset (no Kivy/GUI), same profile as GitHub Actions.
RUN python -m pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r /app/requirements/ci.txt -r /app/requirements/dev.txt

COPY . /app

CMD ["sh", "-c", "ruff check . && pytest -q && pip_audit -r requirements/ci.txt -r requirements/dev.txt"]

