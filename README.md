# PostLayer API

API em FastAPI para autenticação, brand system, creative production e orquestração criativa do `postlayer`.

## Requisitos

- Python 3.11+
- projeto Supabase com Auth e Postgres

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

## Migrations e seeds

```bash
source .venv/bin/activate
alembic upgrade head
```

Para popular templates estruturais de sistema no banco após a migration:

```python
from app.infra.db.seeds import seed_system_layout_templates
from app.infra.db.session import SessionLocal

with SessionLocal() as session:
    created = seed_system_layout_templates(session)
    session.commit()
    print(created)
```

## Variáveis

- `SUPABASE_URL` obrigatória
- `SUPABASE_ANON_KEY` obrigatória
- `SUPABASE_SERVICE_ROLE_KEY` obrigatória
- `DATABASE_URL` obrigatória para o domínio ORM/migrations
- `OPENAI_API_KEY` opcional para provider remoto
- `OPENAI_ENABLE_LIVE_CALLS` default `false` para manter fallback local determinístico
- `POSTLAYER_ALLOWED_ORIGINS` default `http://localhost:3000,http://localhost:8080,http://localhost:5173`

## Supabase

O backend usa:

- Supabase Auth para cadastro, login e validacao do usuario
- PostgREST como camada legada durante a transicao
- Postgres do Supabase como fonte do novo dominio owned pelo backend, com SQLAlchemy 2 e Alembic

Nunca exponha `SUPABASE_SERVICE_ROLE_KEY` no frontend.

## Deploy na Vercel

O projeto ja inclui [vercel.json](/Users/icaroguilherme/Projects/postlayer-api/vercel.json) e [index.py](/Users/icaroguilherme/Projects/postlayer-api/index.py) para o runtime Python da Vercel.

Antes do deploy, configure:

```bash
vercel env add SUPABASE_URL
vercel env add SUPABASE_ANON_KEY
vercel env add SUPABASE_SERVICE_ROLE_KEY
vercel env add DATABASE_URL
vercel env add POSTLAYER_ALLOWED_ORIGINS
```

Depois:

```bash
vercel
vercel --prod
```

## Estrutura

- `app/api`: routers HTTP e dependencies
- `app/application`: contratos e presets compartilhados
- `app/domain`: entidades e enums do dominio
- `app/infra`: integrações externas, config, ORM, migrations e seeds
- `app/schemas`: contratos Pydantic
- `app/orchestration`, `app/rendering`, `app/review_engine`, `app/export_engine`: fundações do pipeline criativo
- `migrations`: trilha Alembic do domínio do produto
