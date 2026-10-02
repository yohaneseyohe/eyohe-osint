# Eyohe OSINT — web

Next.js (App Router, TypeScript strict, Tailwind) workstation UI. Talks to the API through the
same-origin `/api/*` proxy configured in `next.config.ts` (`API_INTERNAL_URL`, default
`http://127.0.0.1:8000`).

```bash
npm install
npm run dev          # http://localhost:3000
npm run typecheck && npm run lint && npm run build
```

See the repository root README and `docs/` for the full picture.
