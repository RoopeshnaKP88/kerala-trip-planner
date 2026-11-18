"""Image preprocessing + VLM location recognition."""
import io
from typing import Optional

from PIL import Image, ImageOps
from pydantic import BaseModel, field_validator

from .llm import ask_json

MAX_WIDTH = 1920

PROMPT = (
    "Analyze this photo. Identify if this is a waterfall or viewpoint in Kerala, India. "
    "Provide the specific name of the location, district, and confidence level. "
    "Return the result strictly in JSON format with fields: "
    'location_name (string), district (string), landmark_type ("waterfall" or "viewpoint"), '
    "confidence (number between 0 and 1), "
    "latitude (number, your best estimate, or null), longitude (number, your best estimate, or null). "
    'If you cannot tell, use location_name "unknown" and confidence 0.'
)


class Recognition(BaseModel):
    location_name: str
    district: str = ""
    landmark_type: str = "viewpoint"
    confidence: float = 0.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_conf(cls, v):
        if isinstance(v, str):
            v = v.strip().lower().rstrip("%")
            words = {"high": 0.9, "medium": 0.6, "low": 0.3}
            if v in words:
                return words[v]
        v = float(v)
        return v / 100 if v > 1 else v

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _coerce_coord(cls, v):
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None


def preprocess(raw: bytes) -> bytes:
    """Fix rotation, force RGB, shrink to max width 1920px, return JPEG bytes."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


async def recognize(image_jpeg: bytes, hint: str | None = None) -> Recognition:
    prompt = PROMPT
    if hint:
        prompt += f" The user says this photo was taken near or in: {hint}."
    data = await ask_json(prompt, image_jpeg)
    return Recognition(**data)