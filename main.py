from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

app = FastAPI(title="DEONIGI MUSIC API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VK_API = "https://api.vk.com/method"
V = "5.131"

# Kate Mobile — unofficially used by many Russian music apps for audio access
CID = "2685278"
CSEC = "VeWdmVclDCtn6ihuP1nt"
UA = "VKAndroidApp/5.52-4543 (Android 5.1.1; SDK 22; x86_64; unknown Android SDK built for x86_64; en; 320x240)"

class AuthData(BaseModel):
    login: str
    password: str

def vk_params(token: str, extra: dict = {}):
    return {"access_token": token, "v": V, **extra}

@app.get("/")
def root():
    return {"status": "DEONIGI MUSIC API running"}

@app.post("/auth")
async def vk_auth(data: AuthData):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            "https://oauth.vk.com/token",
            params={
                "grant_type": "password",
                "client_id": CID,
                "client_secret": CSEC,
                "username": data.login,
                "password": data.password,
                "scope": "audio,offline",
                "v": V,
                "2fa_supported": 1,
            },
            headers={"User-Agent": UA}
        )
        resp = r.json()
        if "error" in resp:
            raise HTTPException(400, resp.get("error_description", resp["error"]))
        return resp

@app.get("/search")
async def search(q: str, token: str, count: int = 30):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"{VK_API}/audio.search",
            params=vk_params(token, {
                "q": q,
                "count": count,
                "sort": 2,
                "auto_complete": 1,
            }),
            headers={"User-Agent": UA}
        )
        data = r.json()
        if "error" in data:
            raise HTTPException(400, str(data["error"]))
        items = data.get("response", {}).get("items", [])
        return {"tracks": [normalize(t) for t in items if t.get("url")]}

@app.get("/popular")
async def popular(token: str, genre_id: int = 0, count: int = 50):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"{VK_API}/audio.getPopular",
            params=vk_params(token, {
                "genre_id": genre_id,
                "count": count,
                "only_eng": 0,
            }),
            headers={"User-Agent": UA}
        )
        data = r.json()
        if "error" in data:
            raise HTTPException(400, str(data["error"]))
        items = data.get("response", [])
        return {"tracks": [normalize(t) for t in items if t.get("url")]}

@app.get("/my")
async def my_audio(token: str, count: int = 200):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"{VK_API}/audio.get",
            params=vk_params(token, {"count": count}),
            headers={"User-Agent": UA}
        )
        data = r.json()
        if "error" in data:
            raise HTTPException(400, str(data["error"]))
        items = data.get("response", {}).get("items", [])
        return {"tracks": [normalize(t) for t in items if t.get("url")]}

@app.get("/artist")
async def artist_tracks(q: str, token: str, count: int = 30):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"{VK_API}/audio.search",
            params=vk_params(token, {
                "q": q,
                "count": count,
                "sort": 0,
                "performer_only": 1,
            }),
            headers={"User-Agent": UA}
        )
        data = r.json()
        items = data.get("response", {}).get("items", [])
        return {"tracks": [normalize(t) for t in items if t.get("url")]}

@app.get("/proxy")
async def proxy_audio(url: str, request: Request):
    headers = {"User-Agent": UA}
    # Forward range header for seeking
    if "range" in request.headers:
        headers["Range"] = request.headers["range"]

    async def generate():
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as c:
            async with c.stream("GET", url, headers=headers) as r:
                async for chunk in r.aiter_bytes(32768):
                    yield chunk

    return StreamingResponse(generate(), media_type="audio/mpeg", headers={
        "Accept-Ranges": "bytes",
        "Access-Control-Allow-Origin": "*",
    })

def normalize(t: dict) -> dict:
    cover = ""
    album = t.get("album", {})
    if album:
        thumb = album.get("thumb", {})
        cover = thumb.get("photo_300") or thumb.get("photo_135") or ""
    return {
        "id": t.get("id"),
        "title": t.get("title", ""),
        "artist": t.get("artist", ""),
        "duration": t.get("duration", 0),
        "url": t.get("url", ""),
        "cover": cover,
    }
