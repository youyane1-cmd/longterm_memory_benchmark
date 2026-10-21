import asyncio
import json
import threading
import time

import httpx
from fastapi import FastAPI, HTTPException, Request
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import AzureCliCredential

app = FastAPI(title="Hello FastAPI")

AZURE_OPENAI_URL = "https://aif-dev-qt-jpe-latc01.services.ai.azure.com/openai/v1/chat/completions"
AZURE_EMBEDDINGS_URL = AZURE_OPENAI_URL.replace("/chat/completions", "/embeddings")
AZURE_AI_SCOPE = "https://ai.azure.com/.default"

credential = AzureCliCredential(process_timeout=30)
token_lock = threading.Lock()
cached_token: str | None = None
cached_token_expires_on = 0
TOKEN_REFRESH_BUFFER_SECONDS = 300


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
            },
            {
                "id": "text-embedding-3-large",
                "object": "model",
                "created": 0,
                "owned_by": "local",
            },
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


@app.post("/v1/embeddings")
async def embeddings(request: Request):
    try:
        body = await request.body()
        message = json.loads(body)

        s = time.time()
        token = await _get_azure_token_async()

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                AZURE_EMBEDDINGS_URL,
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
        print(f"Embedding request failed: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Embedding request failed: {exc}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main_server_openai_embedding:app",
        host="0.0.0.0",
        port=80,
        reload=False,
        workers=1,
    )
