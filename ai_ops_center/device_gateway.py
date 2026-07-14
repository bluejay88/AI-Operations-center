from __future__ import annotations

import argparse
import os
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = ROOT / "laptop_packages"
MAX_REQUEST_BYTES = 131_072


def create_device_gateway(machine_id: str, brain_host: str, token_file: Path) -> FastAPI:
    if machine_id not in {"dev-laptop", "research-laptop", "business-laptop"}:
        raise ValueError("invalid device gateway machine identity")
    token = token_file.read_text(encoding="ascii").strip()
    if len(token) < 32:
        raise RuntimeError("device API token is missing or invalid")
    brain_base = f"http://{brain_host}:8088"
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        client_host = request.client.host if request.client else ""
        if client_host not in {"127.0.0.1", "::1", "testclient"}:
            return Response("loopback access only", status_code=403)
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        return response

    @app.api_route("/api/{path:path}", methods=["GET", "POST"])
    async def proxy(path: str, request: Request) -> Response:
        if not path or ".." in path.split("/"):
            raise HTTPException(status_code=400, detail="invalid proxy path")
        body = await request.body()
        if len(body) > MAX_REQUEST_BYTES:
            raise HTTPException(status_code=413, detail="request body is too large")
        headers = {
            "Authorization": f"Bearer {token}",
            "X-AI-Ops-Device-Id": machine_id,
        }
        if request.headers.get("content-type"):
            headers["Content-Type"] = request.headers["content-type"]
        async with httpx.AsyncClient(timeout=httpx.Timeout(65.0), follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                f"{brain_base}/{path}",
                params=request.query_params,
                content=body or None,
                headers=headers,
            )
        content_type = upstream.headers.get("content-type", "application/json")
        return Response(upstream.content, status_code=upstream.status_code, media_type=content_type.split(";", 1)[0])

    app.mount("/", StaticFiles(directory=PACKAGE_ROOT, html=True), name="device-console")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Loopback-only authenticated AI Operations device dashboard gateway")
    parser.add_argument("--machine", required=True, choices=["dev-laptop", "research-laptop", "business-laptop"])
    parser.add_argument("--brain-host", default="100.70.49.32")
    parser.add_argument("--port", type=int, default=8092)
    parser.add_argument("--token-file", default=str(Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "AI-Ops" / "device-api-token"))
    args = parser.parse_args()
    app = create_device_gateway(args.machine, args.brain_host, Path(args.token_file))
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
