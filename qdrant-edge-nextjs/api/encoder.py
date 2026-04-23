import logging
from pathlib import Path

from fastembed import ImageEmbedding, TextEmbedding
from PIL import Image

from config import TEXT_MODEL_NAME, VISION_MODEL_NAME

logger = logging.getLogger(__name__)


class CrossModalEncoder:
    def __init__(self):
        self.image_model = None
        self.text_model = None

    def load_models(self):
        if self.image_model is None:
            logger.info(f"Loading image model: {VISION_MODEL_NAME}")
            self.image_model = ImageEmbedding(model_name=VISION_MODEL_NAME)
        if self.text_model is None:
            logger.info(f"Loading text model: {TEXT_MODEL_NAME}")
            self.text_model = TextEmbedding(model_name=TEXT_MODEL_NAME)

    def encode_image(self, image):
        if self.image_model is None:
            self.load_models()
        if isinstance(image, (str, Path)):
            image = Image.open(image)
        embeddings = list(self.image_model.embed([image]))
        return embeddings[0]

    def encode_text(self, text: str):
        if self.text_model is None:
            self.load_models()
        embeddings = list(self.text_model.embed([text]))
        return embeddings[0]
