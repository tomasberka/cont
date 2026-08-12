"""Central configuration — everything overridable via environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

USER_AGENT = os.environ.get(
    "CONTENTHUB_USER_AGENT", "HellocompBot/1.0 (info@hellocomp.cz)"
)


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # --- sources ---
    feed_url: str = os.environ.get(
        "SHOPTET_FEED_URL", "https://www.hellocomp.cz/heureka/export/products.xml"
    )
    wikimedia_langs: tuple[str, ...] = ("cs", "en")

    # --- LLM (captioning) ---
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # --- Meta / Instagram publishing ---
    ig_user_id: str = os.environ.get("IG_USER_ID", "")
    ig_access_token: str = os.environ.get("IG_ACCESS_TOKEN", "")
    fb_page_id: str = os.environ.get("FB_PAGE_ID", "")
    # Verified Aug 2026: v26.0 is latest stable; v25.0 available until 2028-07-29.
    graph_api_version: str = os.environ.get("GRAPH_API_VERSION", "v26.0")
    # "facebook" login flow -> graph.facebook.com (needs linked FB Page)
    # "instagram" login flow -> graph.instagram.com (Instagram Login, own account,
    #   scopes instagram_business_basic + instagram_business_content_publish)
    ig_login_flow: str = os.environ.get("IG_LOGIN_FLOW", "instagram")
    # Public base URL where generated media gets uploaded before publishing
    # (e.g. a GitHub release, R2 bucket, or any static host). Empty = dry-run only.
    media_public_base: str = os.environ.get("MEDIA_PUBLIC_BASE", "")

    # --- behaviour ---
    dry_run: bool = _env_bool("DRY_RUN", True)  # SAFE DEFAULT: never publish unless told
    # "carousel" (3 branded slides, default) or "image" (single card)
    post_format: str = os.environ.get("POST_FORMAT", "carousel")
    # carousel visual style: classic | editorial | duotone | auto (rotates daily)
    carousel_style: str = os.environ.get("CAROUSEL_STYLE", "auto")
    # append the raw UTM product URL to captions (URLs aren't clickable on IG;
    # set 0 for cleaner captions once the link-in-bio routine is established)
    caption_link: bool = _env_bool("CAPTION_LINK", True)
    make_reel: bool = _env_bool("MAKE_REEL", False)  # optional extra 9:16 reel
    out_dir: Path = field(default_factory=lambda: REPO_ROOT / "out")
    db_path: Path = field(default_factory=lambda: REPO_ROOT / "data" / "state.db")
    rules_path: Path = field(default_factory=lambda: REPO_ROOT / "data" / "rules.yml")
    bank_path: Path = field(default_factory=lambda: REPO_ROOT / "data" / "facts_bank.yml")
    overrides_path: Path = field(default_factory=lambda: REPO_ROOT / "data" / "overrides.yml")
    fonts_dir: Path = field(default_factory=lambda: REPO_ROOT / "assets" / "fonts")

    # Avoid re-featuring the same product within N days
    product_cooldown_days: int = int(os.environ.get("PRODUCT_COOLDOWN_DAYS", "30"))

    # --- brand ---
    brand_name: str = os.environ.get("BRAND_NAME", "Hellocomp.cz")
    brand_handle: str = os.environ.get("BRAND_HANDLE", "@hellocomp.cz")
    utm: str = os.environ.get(
        "UTM_SUFFIX", "utm_source=instagram&utm_medium=social&utm_campaign=onthisday"
    )

    def ensure_dirs(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
