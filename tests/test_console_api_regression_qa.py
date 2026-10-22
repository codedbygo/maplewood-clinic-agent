"""Regression tests from /qa on 2026-10-22. Report: .gstack/qa-reports/qa-report-localhost-2026-10-22.md"""

from starlette.testclient import TestClient

from console.app import create_app
from tests.test_runner_offline import FakeLLM


# Regression: ISSUE-009 — index.html was cached by the browser, so a new build never reached staff.
# Found by /qa on 2026-10-22
def test_index_is_never_cached_and_hashed_assets_are_immutable(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>console</html>")
    (dist / "assets" / "index-abc123.js").write_text("js")
    app = create_app(results_dir=tmp_path, static_dir=dist, llm_factory=lambda: FakeLLM())
    with TestClient(app) as c:
        for path in ("/", "/inbox", "/index.html"):
            assert "no-cache" in c.get(path).headers.get("cache-control", ""), path
        asset = c.get("/assets/index-abc123.js")
        assert "immutable" in asset.headers.get("cache-control", "")
