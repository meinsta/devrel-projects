import threading
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import (
    VIDEO_PATH,
    DATA_DIR,
    IMAGES_DIR,
    FPS,
    SIMILARITY_THRESHOLD,
    SEARCH_LIMIT,
)
from encoder import CrossModalEncoder
from storage import VisionStorage
from video import VideoCapture

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SystemState:
    def __init__(self):
        self.is_running = True
        self.is_indexing = False
        self.frames_indexed = 0
        self.encoder = None
        self.storage = None

    def initialize(self):
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        self.storage = VisionStorage(DATA_DIR)
        self.storage.initialize()

        self.encoder = CrossModalEncoder()
        self.encoder.load_models()

        threading.Thread(target=self.index_video_background, daemon=True).start()

    def index_video_background(self):
        if not VIDEO_PATH.exists():
            logger.warning(f"Video not found: {VIDEO_PATH}")
            return

        self.is_indexing = True
        cap = VideoCapture(str(VIDEO_PATH), fps=FPS)
        last_frame = None

        with cap:
            for frame in cap.capture_continuous():
                if not self.is_running:
                    break

                if last_frame is not None:
                    if VideoCapture.calculate_similarity(frame, last_frame) > SIMILARITY_THRESHOLD:
                        continue

                last_frame = frame
                timestamp = int(time.time() * 1000)
                image_path = IMAGES_DIR / f"frame_{timestamp}.jpg"

                cap.save_frame(frame, image_path)
                embedding = self.encoder.encode_image(image_path)
                self.storage.store_image(image_path, embedding)
                self.frames_indexed += 1

        self.is_indexing = False
        logger.info(f"Indexing complete. Total frames: {self.frames_indexed}")


state = SystemState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.initialize()
    yield
    state.is_running = False
    if state.storage:
        state.storage.stop()


app = FastAPI(title="Qdrant Edge Visual Search API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    limit: int = SEARCH_LIMIT


class SearchResult(BaseModel):
    id: str
    score: float
    image_url: str
    timestamp: str


class StatusResponse(BaseModel):
    is_indexing: bool
    frames_indexed: int
    queue_size: int


@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    return StatusResponse(
        is_indexing=state.is_indexing,
        frames_indexed=state.frames_indexed,
        queue_size=state.storage.get_indexed_count() if state.storage else 0,
    )


@app.post("/api/search", response_model=list[SearchResult])
async def search(request: SearchRequest):
    if not state.encoder or not state.storage:
        raise HTTPException(status_code=503, detail="System not initialized")

    text_embedding = state.encoder.encode_text(request.query)
    results = state.storage.search_similar(text_embedding, limit=request.limit)

    return [
        SearchResult(
            id=str(r["id"]),
            score=r["score"],
            image_url=f"/api/images/{Path(r['image_path']).name}",
            timestamp=r["timestamp"],
        )
        for r in results
    ]


@app.get("/api/images/{filename}")
async def get_image(filename: str):
    image_path = IMAGES_DIR / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path, media_type="image/jpeg")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7777)
