# PostLayer API

API em FastAPI para autenticação, organizações, identidade visual, posts, templates e geração simples de background para o frontend `postlayer`.

## Requisitos

- Python 3.11+
- projeto Supabase com Auth + PostgREST

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

## Variáveis

- `SUPABASE_URL` obrigatória
- `SUPABASE_ANON_KEY` obrigatória
- `SUPABASE_SERVICE_ROLE_KEY` obrigatória
- `POSTLAYER_ALLOWED_ORIGINS` default `http://localhost:8080,http://localhost:5173`

## Supabase

O backend usa:

- Supabase Auth para cadastro, login e validacao do usuario
- PostgREST com `service_role` no servidor para ler e escrever nas tabelas

Nunca exponha `SUPABASE_SERVICE_ROLE_KEY` no frontend.

## Deploy na Vercel

O projeto ja inclui [vercel.json](/Users/icaroguilherme/Projects/postlayer-api/vercel.json) e [index.py](/Users/icaroguilherme/Projects/postlayer-api/index.py) para o runtime Python da Vercel.

Antes do deploy, configure:

```bash
vercel env add SUPABASE_URL
vercel env add SUPABASE_ANON_KEY
vercel env add SUPABASE_SERVICE_ROLE_KEY
vercel env add POSTLAYER_ALLOWED_ORIGINS
```

Depois:

```bash
vercel
vercel --prod
```
