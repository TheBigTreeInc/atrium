"""Disposable authoritative DAPI startup smoke; runs only with pinned DAPI installed.

Never touches the operator's persistent data, sources or server.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def main():
    try:
        from looprd.config import Settings
        from looprd.app import create_app
        from starlette.testclient import TestClient
    except ImportError as error:
        raise SystemExit(f"Install the pinned DAPI runtime before smoke: {error}")
    with TemporaryDirectory(prefix="atrium-p0-smoke-") as work:
        temp = Path(work)
        (temp / "secrets").mkdir()
        settings = Settings(
            sources=str(ROOT / "examples" / "sources.local.yaml"),
            data=temp / "data",
            secrets=temp / "secrets",
            poll_seconds=3600,
            bootstrap_admin=False,
            allow_python=True,
            trusted_components=("atrium",),
        )
        app = create_app(settings=settings)
        with TestClient(app) as client:
            assert client.get("/_looprd/health").status_code == 200
            runtime = app.state.runtime
            assert "atrium" in runtime.active, (
                f"Atrium did not activate: {runtime.errors!r}; sources={runtime.sources_error!r}"
            )
            spec = runtime.active["atrium"].spec
            assert spec.component == "atrium" and spec.release == "0.3.0"
            assert "apps" in spec.resources and "tables" in spec.resources
            assert "snapshots" in spec.resources
            # No provisioned caller key: even informational component routes must deny guests.
            unauthorized = client.get("/looprd/atrium/v1/info")
            assert unauthorized.status_code == 401, unauthorized.text
    print("Disposable DAPI activation: active atrium v0.3.0; guest component requests denied")


if __name__ == "__main__":
    main()
