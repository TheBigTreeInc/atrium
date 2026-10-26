"""Bounded protected LoopRD handler. Promote ONLY after generic anonymous-handler support."""
from sqlalchemy import text as _hosted_sql
from starlette.exceptions import HTTPException as _HostHTTPException

async def hosted_games_from_looprd(ctx):
    if ctx.session_factory is None:
        raise _HostHTTPException(status_code=503, detail='hosted_catalog_unavailable')
    try:
        # A fresh read inside the owning Atrium component's authenticated DB.
        with ctx.session_factory() as session:
            rows = session.execute(_hosted_sql(HOSTED_ROWS_QUERY)).mappings().all()
        return project_hosted_games(rows)
    except Exception as exc:
        # A malformed/unavailable row must never publish partial or stale data.
        # Preserve HTTP cancellation/critical interpreter exceptions.
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise _HostHTTPException(status_code=503, detail='hosted_catalog_unavailable') from None
