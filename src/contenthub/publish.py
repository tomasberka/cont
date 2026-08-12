"""Instagram publishing via Meta's API — dry-run by default.

Verified Aug 2026:
- Two login flavors share endpoint *paths* but differ in host + scopes:
    "instagram" flow -> https://graph.instagram.com  (Instagram Login;
        scopes instagram_business_basic + instagram_business_content_publish;
        publishing to YOUR OWN professional account works on standard access)
    "facebook" flow  -> https://graph.facebook.com   (needs linked FB Page;
        scopes instagram_basic + instagram_content_publish + pages_read_engagement)
- Pin a recent version: v26.0 (latest) / v25.0 (supported until 2028-07-29).
- Two-step flow unchanged: POST /{ig_id}/media -> poll status -> /media_publish.
- Media must be at a PUBLIC https URL (MEDIA_PUBLIC_BASE + filename).
- Limit: 100 API-published posts per rolling 24 h; check /content_publishing_limit.
"""
from __future__ import annotations

import logging
import time

import requests

from .config import Config

log = logging.getLogger(__name__)


def _base(cfg: Config) -> str:
    host = (
        "graph.instagram.com" if cfg.ig_login_flow == "instagram" else "graph.facebook.com"
    )
    return f"https://{host}/{cfg.graph_api_version}"


class PublishResult:
    def __init__(self, published: bool, media_id: str | None, note: str):
        self.published = published
        self.media_id = media_id
        self.note = note


def publish_image(cfg: Config, image_public_url: str, caption: str) -> PublishResult:
    return _publish(cfg, {"image_url": image_public_url, "caption": caption})


def publish_carousel(cfg: Config, image_public_urls: list[str], caption: str) -> PublishResult:
    """Carousel = child containers (is_carousel_item) + one CAROUSEL parent.
    Counts as a single post against the 100/24h limit."""
    if cfg.dry_run or not (cfg.ig_user_id and cfg.ig_access_token):
        note = "DRY RUN — carousel not sent to Instagram"
        if not cfg.dry_run:
            note = "Missing IG_USER_ID/IG_ACCESS_TOKEN — treated as dry run"
        log.info("%s | %d slides", note, len(image_public_urls))
        return PublishResult(False, None, note)

    base = _base(cfg)
    tok = {"access_token": cfg.ig_access_token}
    children: list[str] = []
    for url in image_public_urls:
        r = requests.post(f"{base}/{cfg.ig_user_id}/media",
                          data={"image_url": url, "is_carousel_item": "true", **tok},
                          timeout=120)
        r.raise_for_status()
        children.append(r.json()["id"])
    return _publish(
        cfg,
        {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption},
        _skip_guard=True,
    )


def publish_reel(cfg: Config, video_public_url: str, caption: str) -> PublishResult:
    return _publish(
        cfg,
        {"media_type": "REELS", "video_url": video_public_url, "caption": caption},
        poll=True,
    )


def _publish(cfg: Config, media_params: dict, poll: bool = False,
             _skip_guard: bool = False) -> PublishResult:
    if not _skip_guard and (cfg.dry_run or not (cfg.ig_user_id and cfg.ig_access_token)):
        note = "DRY RUN — nothing sent to Instagram"
        if not cfg.dry_run:
            note = "Missing IG_USER_ID/IG_ACCESS_TOKEN — treated as dry run"
        log.info("%s | params=%s", note, {k: v for k, v in media_params.items() if k != "caption"})
        return PublishResult(False, None, note)

    base = _base(cfg)
    tok = {"access_token": cfg.ig_access_token}

    # 1) create container
    r = requests.post(f"{base}/{cfg.ig_user_id}/media",
                      data={**media_params, **tok}, timeout=120)
    r.raise_for_status()
    container_id = r.json()["id"]

    # 2) poll container status (required for video; harmless for images)
    if poll:
        for _ in range(40):
            st = requests.get(f"{base}/{container_id}",
                              params={"fields": "status_code", **tok}, timeout=30).json()
            code = st.get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                return PublishResult(False, None, f"Container error: {st}")
            time.sleep(15)
        else:
            return PublishResult(False, None, "Container never reached FINISHED")

    # 3) publish
    r = requests.post(f"{base}/{cfg.ig_user_id}/media_publish",
                      data={"creation_id": container_id, **tok}, timeout=120)
    r.raise_for_status()
    media_id = r.json().get("id")
    log.info("Published to Instagram: media_id=%s", media_id)
    return PublishResult(True, media_id, "published")


def refresh_long_lived_token(cfg: Config) -> str | None:
    """Refresh a long-lived token before its 60-day expiry (run weekly).

    Instagram Login flow: GET /refresh_access_token (no app secret needed).
    Facebook flow: exchange via /oauth/access_token with app id+secret.
    """
    if not cfg.ig_access_token:
        return None
    if cfg.ig_login_flow == "instagram":
        r = requests.get(
            "https://graph.instagram.com/refresh_access_token",
            params={"grant_type": "ig_refresh_token",
                    "access_token": cfg.ig_access_token},
            timeout=60,
        )
        if r.ok:
            return r.json().get("access_token")
        log.error("Token refresh failed: %s", r.text[:400])
    else:
        log.warning("Facebook-flow token refresh needs app id+secret — see runbook")
    return None
