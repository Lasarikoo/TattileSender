from datetime import datetime

import app.utils.images as images


def test_resolve_image_path_supports_relative_and_legacy(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "IMAGES_BASE", tmp_path)
    monkeypatch.setattr(images.settings, "images_dir", str(tmp_path))

    rel_path = "2001008851/2025/12/01/20251201175430_plate-ABC123_ocr.jpg"
    legacy_path = f"data/images/{rel_path}"
    abs_path = tmp_path / "absolute.jpg"
    abs_path.touch()

    assert images.resolve_image_path(rel_path) == tmp_path / rel_path
    assert images.resolve_image_path(legacy_path) == tmp_path / rel_path
    assert images.resolve_image_path(str(abs_path)) == abs_path


def test_build_image_paths_returns_relative_and_full_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "IMAGES_BASE", tmp_path)
    monkeypatch.setattr(images.settings, "images_dir", str(tmp_path))

    ts = datetime(2025, 12, 1, 17, 54, 30)
    rel_ocr, rel_ctx, full_ocr, full_ctx = images.build_image_paths(
        "2001008851", ts, "4225LTV"
    )

    expected_rel = "2001008851/2025/12/01/20251201175430_plate-4225LTV"
    assert rel_ocr == f"{expected_rel}_ocr.jpg"
    assert rel_ctx == f"{expected_rel}_ctx.jpg"
    assert full_ocr == tmp_path / rel_ocr
    assert full_ctx == tmp_path / rel_ctx
    assert full_ocr.parent.exists()
    assert full_ctx.parent.exists()
