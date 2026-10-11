from pathlib import Path

from app.core.config import get_settings
from app.services import asset_storage


def test_local_asset_storage_round_trip(tmp_path: Path) -> None:
    settings = get_settings()
    original_backend = settings.asset_storage_backend
    original_path = settings.asset_storage_local_path
    try:
        settings.asset_storage_backend = "local"
        settings.asset_storage_local_path = str(tmp_path)
        stored = asset_storage.put_bytes(
            "org/assets/asset-1/version-1-cover.png", b"png-bytes", "image/png"
        )
        assert stored.file_size == 9
        assert stored.content_type == "image/png"

        content, detected_type = asset_storage.get_bytes(stored.object_key)
        assert content == b"png-bytes"
        assert detected_type == "application/octet-stream"
        asset_storage.delete_object(stored.object_key)
        assert not (tmp_path / "org/assets/asset-1/version-1-cover.png").exists()
    finally:
        settings.asset_storage_backend = original_backend
        settings.asset_storage_local_path = original_path
