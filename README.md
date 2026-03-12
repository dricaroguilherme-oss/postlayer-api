# PostLayer API

API em FastAPI para autenticação, organizações, identidade visual, posts, templates e geração simples de background para o frontend `postlayer`.

## Requisitos

- Python 3.11+

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

## Variáveis opcionais

- `POSTLAYER_API_HOST` default `0.0.0.0`
- `POSTLAYER_API_PORT` default `8000`
- `POSTLAYER_API_SECRET` default `dev-secret-change-me-and-make-it-longer`
- `POSTLAYER_API_DB_PATH` default `postlayer.db`
- `POSTLAYER_ALLOWED_ORIGINS` default `http://localhost:8080,http://localhost:5173`
