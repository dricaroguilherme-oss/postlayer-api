# ADR 0001: Next.js App Router for PostLayer Frontend

- Status: accepted
- Context: the product needs file-system routing, strong server/client boundaries and a clearer path to preview deployments and future server actions.
- Decision: rewrite the frontend in-place from Vite/React Router to Next.js App Router while keeping the existing visual language.
- Consequences: routing and env handling change immediately; old Vite-only entrypoints are removed and the new foundation favors structured feature modules.
