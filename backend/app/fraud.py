import random, datetime, asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

def make_event():
    fraud = random.random() < 0.02
    return {
        "ts": datetime.datetime.utcnow().isoformat()+"Z",
        "user_id": random.randint(1000, 9999),
        "amount": round(random.uniform(1, 5000), 2),
        "location": random.choice(["NY","LA","SF","CHI","MIA"]),
        "label": "fraud" if fraud else "legit"
    }

@router.get("/demo")
async def demo():
    return {"demo": True, "events": [make_event() for _ in range(10)]}

@router.get("/full")
async def full():
    async def generator():
        while True:
            batch = [make_event() for _ in range(10)]
            for ev in batch:
                yield f"data: {ev}\n\n"
            await asyncio.sleep(0.001)   # 10 k events per second
    return StreamingResponse(generator(), media_type="text/event-stream")
