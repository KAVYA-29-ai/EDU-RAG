# 01 — About the Project

MINIRAG2 is an enterprise knowledge intelligence platform that combines semantic search and Retrieval-Augmented Generation (RAG) to provide accurate, source-backed answers over company documents and knowledge bases.

Key goals
- Provide reliable, explainable answers that reference source documents.
- Make search and Q&A accessible to non-technical users via a responsive web UI.
- Offer hooks for feedback, analytics and continuous improvement.

Primary users
- Internal teams (support, product, engineering) searching internal docs.
- Educators and students for knowledge retrieval and tutoring use-cases.

Live deployment
- The frontend is deployed to Vercel; backend APIs are available under `/api` (see `deployment.md` and Vercel project settings).

Project layout (short)
- `backend/` — Python backend with routers and RAG orchestration.
- `src/` — React frontend source.
- `documentation/` — this folder.
