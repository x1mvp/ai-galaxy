import os
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
import asyncpg, asyncio
from pgvector.asyncpg import register_vector
from openai import AsyncOpenAI

router = APIRouter()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
PG_URL     = os.getenv("PGVECTOR_URL")

if not OPENAI_KEY or not PG_URL:
    raise RuntimeError("Missing env vars")

client = AsyncOpenAI(api_key=OPENAI_KEY)

class Query(BaseModel):
    q: str

class RAGEngine:
    def __init__(self):
        self.conn = None

    async def _conn(self):
        if self.conn is None:
            self.conn = await asyncpg.connect(PG_URL)
            await register_vector(self.conn)

    async def _embed(self, txt: str):
        resp = await client.embeddings.create(
            model="text-embedding-3-large",
            input=txt,
        )
        return resp.data[0].embedding

    async def _search(self, vec, k=5):
        await self._conn()
        rows = await self.conn.fetch(
            """
            SELECT lead_name, lead_company, lead_role, source
            FROM leads
            ORDER BY embedding <=> $1
            LIMIT $2;
            """,
            vec, k,
        )
        return [dict(r) for r in rows]

    async def answer(self, q: str):
        vec = await self._embed(q)
        hits = await self._search(vec)
        lead_list = "\n".join(
            f"- {h['lead_name']} ({h['lead_company']}, {h['lead_role']})"
            for h in hits
        )
        prompt = f"""You are a sales assistant. The user asked:

"{q}"

Relevant leads:
{lead_list}

Give a short (2‑3 sentence) answer that points out the best match and why."""
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()

    async def demo(self, n=3):
        await self._conn()
        rows = await self.conn.fetch(
            "SELECT lead_name, lead_company FROM leads ORDER BY random() LIMIT $1;", n
        )
        return [dict(r) for r in rows]

engine = RAGEngine()

@router.post("/demo")
async def demo(q: Query):
    leads = await engine.demo()
    return {"demo": True, "leads": leads}

@router.post("/full")
async def full(q: Query, _: bool = Depends(Depends)):
    ans = await engine.answer(q.q)
    return {"demo": False, "answer": ans}
