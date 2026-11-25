# Architecture decisions
1. **Auth lives in FastAPI, not Auth.js/Better Auth.** Those libraries run inside Node/Next.js; using them would make the backend depend on the frontend, which the spec forbids. Argon2 + opaque session tokens (SHA-256 hash stored; raw token only in an HttpOnly cookie).
2. **Sessions over JWT**: revocable on logout, no key-rotation issues.
3. **Authorization**: `project_for_user` / `document_for_user` in api/deps.py are the only way routes load tenant data. Foreign IDs return 404.
4. **Sync SQLAlchemy 2.0 + psycopg3**: simpler; heavy work runs in the worker anyway.
5. **Neon**: use the pooled connection string; the migration env enables pgvector.
