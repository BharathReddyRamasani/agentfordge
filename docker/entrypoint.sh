#!/bin/sh
# Container entrypoint: apply database migrations, then execute the service command.
set -e
alembic upgrade head
exec "$@"
