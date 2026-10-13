"""Docker tool: availability check and deployment config generation for generated apps."""

from app.core.config import settings
from app.tools.terminal import run_command


def docker_available() -> bool:
    result = run_command(["docker", "--version"], timeout=15)
    return result.ok


def sanitize_service_name(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-") or "app"


def dockerfile_content(app_name: str) -> str:
    return f"""FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
ENV DATABASE_URL=sqlite:///./data/app.db
RUN mkdir -p data
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
"""


def compose_content(app_name: str) -> str:
    service = sanitize_service_name(app_name)
    return f"""services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: {service}
    volumes:
      - {service}_pgdata:/var/lib/postgresql/data

  app:
    build:
      context: ..
      dockerfile: deployment/Dockerfile
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/{service}
    ports:
      - "8001:8001"
    depends_on:
      - db

volumes:
  {service}_pgdata:
"""


def env_template_content() -> str:
    return """DATABASE_URL=sqlite:///./data/app.db
JWT_SECRET=change-me
"""


def start_script_content() -> str:
    return """@echo off
pip install -r backend/requirements.txt
python -m uvicorn main:app --reload --port 8001
"""


def validate_deployment_files(files: dict[str, str]) -> list[str]:
    issues = []
    required = ["Dockerfile", "docker-compose.yml"]
    for name in required:
        if name not in files:
            issues.append(f"Missing deployment file: {name}")
    if "Dockerfile" in files and "FROM" not in files["Dockerfile"]:
        issues.append("Dockerfile has no base image")
    if settings.llm_api_key and "llm_api_key" in str(files).lower().replace("llm_api_key=", ""):
        pass
    return issues
