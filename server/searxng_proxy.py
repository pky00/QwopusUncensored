#!/usr/bin/env python3
"""HTTPS + API key proxy in front of SearXNG.
SearXNG has no built-in auth, so this proxy validates the same
API key used by vLLM and forwards requests to localhost:8888.
"""
import os
import ssl
import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

API_KEY = os.environ["QWOPUS_API_KEY"]
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888")
PROXY_PORT = int(os.environ.get("SEARXNG_PROXY_PORT", "8889"))
SSL_CERT = os.environ.get("SSL_CERTFILE", "/etc/letsencrypt/live/{}/fullchain.pem")
SSL_KEY = os.environ.get("SSL_KEYFILE", "/etc/letsencrypt/live/{}/privkey.pem")
DOMAIN = os.environ.get("QWOPUS_DOMAIN", "qwopus.peteryamout.com")

app = FastAPI()
client = httpx.AsyncClient(base_url=SEARXNG_URL, timeout=30.0)


def _check_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if auth == f"Bearer {API_KEY}":
        return True
    api_key_param = request.query_params.get("api_key", "")
    return api_key_param == API_KEY


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request, path: str):
    if not _check_auth(request):
        return JSONResponse(status_code=401, content={"error": "Invalid API key"})

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "authorization")
    }

    body = await request.body()
    params = dict(request.query_params)
    params.pop("api_key", None)

    response = await client.request(
        method=request.method,
        url=f"/{path}",
        headers=headers,
        params=params,
        content=body,
    )

    return JSONResponse(
        status_code=response.status_code,
        content=response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    cert_path = SSL_CERT.format(DOMAIN)
    key_path = SSL_KEY.format(DOMAIN)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PROXY_PORT,
        ssl_keyfile=key_path,
        ssl_certfile=cert_path,
    )
