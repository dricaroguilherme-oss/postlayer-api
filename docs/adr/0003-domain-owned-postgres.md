# ADR 0003: Backend-owned Product Domain on Supabase Postgres

- Status: accepted
- Context: Supabase Auth remains useful, but the creative domain needs stronger versioning, migrations and bounded-context ownership.
- Decision: keep Supabase Auth and managed Postgres, but move the product schema, migrations and domain persistence under the FastAPI backend.
- Consequences: PostgREST usage becomes transitional; new product entities are introduced through ORM + Alembic and consumed via backend APIs.
