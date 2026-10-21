import asyncio
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import AzureCliCredential

app = FastAPI(title="Hello FastAPI")

EMBEDDING_URL = "http://10.110.159.5:8600/v2/models/emb_pipeline/infer"
AZURE_OPENAI_URL = "https://aif-dev-qt-jpe-latc01.services.ai.azure.com/openai/v1/chat/completions"
AZURE_AI_SCOPE = "https://ai.azure.com/.default"

credential = AzureCliCredential(process_timeout=30)
token_lock = threading.Lock()
cached_token: str | None = None
cached_token_expires_on = 0
TOKEN_REFRESH_BUFFER_SECONDS = 300



class EmbeddingRequest(BaseModel):
    model: str | None = None
    input: list[str]


@app.get("/")
def read_root():
    return {"message": "Hello World"}


def _get_azure_token(retries: int = 2) -> str:
    global cached_token, cached_token_expires_on

    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            now = time.time()
            if cached_token and now < cached_token_expires_on - TOKEN_REFRESH_BUFFER_SECONDS:
                return cached_token

            with token_lock:
                now = time.time()
                if cached_token and now < cached_token_expires_on - TOKEN_REFRESH_BUFFER_SECONDS:
                    return cached_token

                access_token = credential.get_token(AZURE_AI_SCOPE)
                cached_token = access_token.token
                cached_token_expires_on = access_token.expires_on
                return cached_token
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(1)

    raise HTTPException(
        status_code=503,
        detail=f"Azure authentication failed: {last_exc}",
    )


async def _get_azure_token_async() -> str:
    return await asyncio.to_thread(_get_azure_token)


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-5.4-mini",
                "object": "model",
                "created": 0,
                "owned_by": "local",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def comletions(request: Request):
    try:
        body = await request.body()
        message = json.loads(body)
        message.pop("max_tokens", None)

        s = time.time()
        token = await _get_azure_token_async()

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                AZURE_OPENAI_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                json=message,
            )

        response.raise_for_status()
        data = response.json()
        print(time.time() - s)
        return data

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON body: {exc}",
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        )
    except ClientAuthenticationError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Azure authentication failed: {exc}",
        )
    except HTTPException:
        raise
    except Exception as exc:
        print(f"OpenAI request failed: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI request failed: {exc}",
        )


def _normalize_embeddings(emb_data: list[Any], shape: list[int]) -> list[Any]:
    if not shape or len(shape) < 2:
        return emb_data

    batch_size, dimension = shape[0], shape[1]

    if batch_size <= 0 or dimension <= 0:
        return []

    if emb_data and isinstance(emb_data[0], list):
        return emb_data

    expected_size = batch_size * dimension
    if len(emb_data) != expected_size:
        return emb_data

    return [
        emb_data[index * dimension: (index + 1) * dimension]
        for index in range(batch_size)
    ]


@app.post("/v1/embeddings")
def embeddings(item: EmbeddingRequest):
    if not item.input:
        raise HTTPException(status_code=422, detail="'input' cannot be empty.")

    payload = {
        "inputs": [
            {
                "name": "text_input",
                "shape": [len(item.input)],
                "datatype": "BYTES",
                "data": item.input,
            }
        ],
        "outputs": [{"name": "embeddings"}],
    }

    request_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        EMBEDDING_URL,
        data=request_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Embedding service returned HTTP {exc.code}: {exc.reason}",
        )
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Embedding service request failed: {exc.reason}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected embedding error: {exc}",
        )

    outputs = result.get("outputs") or []
    if not outputs:
        raise HTTPException(
            status_code=502,
            detail="Embedding service response does not contain 'outputs'.",
        )

    output = outputs[0]
    emb_data = output.get("data") or []
    shape = output.get("shape") or []

    embeddings = _normalize_embeddings(emb_data, shape)

    return {
        "object": "list",
        "data": [
            {
                "index": index,
                "embedding": embedding,
            }
            for index, embedding in enumerate(embeddings)
        ],
        "model": item.model,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main_server:app",
        host="0.0.0.0",
        port=80,
        reload=False,
        workers=1,
    )