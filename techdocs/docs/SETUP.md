cp .env.example .env
docker compose up -d db
docker compose run --rm api alembic revision --autogenerate -m "initial schema"
docker compose up api
docker compose run --rm api pytest
