from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).parent.parent.absolute()

VIDEO_PATH = PROJECT_ROOT / "public" / "video.mp4"
DATA_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"

FPS = 1.0
JPEG_QUALITY = 70
SIMILARITY_THRESHOLD = 0.75

VISION_MODEL_NAME = "Qdrant/clip-ViT-B-32-vision"
TEXT_MODEL_NAME = "Qdrant/clip-ViT-B-32-text"
VECTOR_DIMENSION = 512

VECTOR_NAME = "vision"
SEARCH_LIMIT = 6
MMR_DIVERSITY_FACTOR = 0.8
MMR_MAX_CANDIDATES = 100
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "visual_search"
SYNC_INTERVAL = 5
