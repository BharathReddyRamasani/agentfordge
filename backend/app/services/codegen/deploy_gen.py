"""Deployment Agent codegen: generates real deployment configuration for the generated app."""

from app.tools.docker_tool import (
    compose_content,
    dockerfile_content,
    env_template_content,
    start_script_content,
)


def generate_deployment_files(app_name: str) -> dict[str, str]:
    return {
        "deployment/Dockerfile": dockerfile_content(app_name),
        "deployment/docker-compose.yml": compose_content(app_name),
        "deployment/.env.example": env_template_content(),
        "deployment/start.bat": start_script_content(),
        "deployment/start.sh": start_script_content().replace("@echo off\n", "#!/bin/sh\n"),
    }
