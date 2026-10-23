"""Freeze Market Grove's tested game engine into an independent LoopRD component.

Never use root includes: they merge into Atrium's privileged component.
"""
from pathlib import Path
import argparse
import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'games/market-grove/looprd.base.yaml'
OUT = ROOT/'games/market-grove/looprd.yaml'
ENGINE = ROOT/'games/market-grove/game/engine.py'

class Literal(str):
    pass


OPERATIONS = {
    '/market/state': 'snapshot',
    '/market/order': 'order',
    '/market/cancel': 'cancel',
    '/market/history': 'history',
    '/market/activity': 'activity',
    '/market/investments': 'wallet_projection',
}

ADAPTER = '''
# The LoopRD home realm owns auth and storage; the demo-session endpoint is never exposed.
# Only a verified LoopRD database-auth principal can reach these handlers.
def market_from_context(ctx):
    from starlette.exceptions import HTTPException
    with ctx.session_factory() as session:
        bind = session.get_bind()
        if not bind.url.drivername.startswith('sqlite') or not bind.url.database or bind.url.database == ':memory:':
            raise HTTPException(status_code=503, detail='market_storage_unavailable')
        path = bind.url.database
    return Market(path, interval_seconds=3600, seed_demo_players=False)

def service_player(ctx, market):
    from starlette.exceptions import HTTPException
    try:
        return market.ensure_service_player(ctx.principal.id)
    except MarketError:
        raise HTTPException(status_code=401, detail='unauthorized')

async def dispatch_market(ctx, action):
    from starlette.concurrency import run_in_threadpool
    from starlette.exceptions import HTTPException
    def execute():
        try:
            market = market_from_context(ctx)
            user = service_player(ctx, market)
            if action == 'snapshot': return market.snapshot(user)
            if action == 'order': return market.order(user, ctx.body)
            if action == 'cancel':
                if not isinstance(ctx.body, dict) or set(ctx.body) != {'orderId'}:
                    raise MarketError(422, 'invalid_cancel')
                return market.cancel(user, ctx.body['orderId'])
            if action == 'history': return market.history(ctx.request.query_params.get('symbol', 'CEDR'))
            if action == 'activity': return market.activity(user)
            if action == 'wallet_projection': return market.wallet_projection(user)
            raise MarketError(404, 'unknown_action')
        except MarketError as e:
            raise HTTPException(status_code=e.status, detail=e.code)
    return await run_in_threadpool(execute)
'''

JOB = '''
from starlette.concurrency import run_in_threadpool
async def handle(ctx):
    def tick():
        m=market_from_context(ctx)
        m.settle_due()
        return {'status':'settled_or_current'}
    return await run_in_threadpool(tick)
'''


def render():
    spec = yaml.safe_load(BASE.read_text(encoding='utf-8'))
    engine = ENGINE.read_text(encoding='utf-8')
    # Engine has one future import; keep at start of generated modules.
    common=engine+'\n'+ADAPTER
    for handler in spec['handlers']:
        action=OPERATIONS[handler['path']]
        handler['source']=Literal(common+f'\nasync def handle(ctx):\n    return await dispatch_market(ctx, {action!r})\n')
    spec['jobs']['clear-market']['source']=Literal(common+JOB)
    class Dumper(yaml.SafeDumper): pass
    Dumper.add_representer(Literal,lambda d,s:d.represent_scalar('tag:yaml.org,2002:str',str(s),style='|'))
    return yaml.dump(spec,Dumper=Dumper,sort_keys=False,allow_unicode=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
    expected=render()
    if args.check:
        if OUT.read_text(encoding='utf-8')!=expected: raise SystemExit('Market Grove LoopRD spec stale; rerun generator')
        print('Market Grove LoopRD descriptor matches source')
    else:
        OUT.write_text(expected,encoding='utf-8');print('Generated standalone Market Grove LoopRD component')

if __name__=='__main__':main()
