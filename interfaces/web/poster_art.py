"""What a poster illustration is made of: availability, prompt, client, cost log."""

from __future__ import annotations

from loguru import logger

from config import Config
from interfaces.web.poster_errors import PosterFailedError
from interfaces.web.schemas_library import Playbill
from llm.image_client import GeneratedImage, ImageClient, OpenAIImageClient

POSTER_AGENT = "PosterIllustrator"


def posters_available(cfg: Config) -> bool:
    """Return whether players may request poster illustrations."""
    return cfg.poster_images_enabled and bool(cfg.openai_api_key)


def default_image_client(cfg: Config) -> ImageClient:
    """Build the configured OpenAI image client."""
    return OpenAIImageClient(
        api_key=cfg.openai_api_key or "",
        model=cfg.poster_image_model,
        quality=cfg.poster_image_quality,
    )


def poster_prompt(playbill: Playbill) -> str:
    """Compose the illustration prompt from the playbill.

    Cast names are deliberately left out: the picture shows the hero and the
    place, and the typography (title, tagline, cast) is drawn by the client.
    """
    place = playbill.place or playbill.region
    hero = playbill.hero_look or "a lone traveller"
    return (
        "Illustrated vintage theatre poster for an interactive story. "
        "Setting: {0} ({1}, {2}). Scene: {3}, {4}. Hero: {5}. Mood: {6} "
        "Painterly, dramatic stage lighting, rich deep colours, portrait composition, "
        "the hero small against the place. No text, no letters, no captions, no logos."
    ).format(playbill.setting, playbill.era, playbill.region, place, playbill.daypart, hero, playbill.tagline)


def cost_log_entry(session_id: str, prompt: str, image: GeneratedImage) -> dict[str, object]:
    """Describe one illustration as an ``ai_call_logs`` row for spend reports and quotas."""
    return {
        "session_id": session_id,
        "agent_name": POSTER_AGENT,
        "model": image.model,
        "system_prompt": "",
        "messages": [{"role": "user", "content": prompt}],
        "response_content": "[{0} image, {1} bytes]".format(image.mime, len(image.image_bytes)),
        "prompt_tokens": image.input_tokens,
        "completion_tokens": image.output_tokens,
        "duration_ms": image.duration_ms,
    }


async def paint(client: ImageClient, prompt: str) -> GeneratedImage:
    """Generate the illustration, turning any provider failure into ``PosterFailedError``."""
    try:
        return await client.generate(prompt)
    except Exception as exc:
        logger.exception("Poster illustration failed at the image provider")
        raise PosterFailedError("image provider failed") from exc
