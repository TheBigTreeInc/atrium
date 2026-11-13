"""Atrium Market Grove exchange extension: fictional instruments, bounded matching and bots.

This module is source-inlined into the independent LoopRD child by the generator.
Never contains a live-wallet settlement capability or fiat/commodity trading endpoint.
"""

import hashlib

ADDITIONAL_COMPANIES = (
    ('WAVE','Wavecrest Media','Entertainment',72,'◉'),('NOVA','Nova Aerospace','Technology',185,'✧'),
    ('GRDN','Garden Guild','Consumer',63,'❀'),('VOLT','Voltara','Energy',115,'ϟ'),
    ('NEXO','Nexora Systems','Technology',132,'◆'),('ORBT','Orbital Freight','Transport',88,'◌'),
    ('ALPN','Alpine Foods','Consumer',67,'△'),('SAGE','Sage Health','Healthcare',102,'✚'),
    ('BRCK','Brickhouse','Construction',81,'▣'),('GLIM','Glimmer Studios','Entertainment',54,'✷'),
    ('RIVR','Riverbank','Services',121,'≈'),('SPRK','Spark Foundry','Industry',94,'✦'),
    ('COVE','Coastal Resorts','Leisure',77,'◈'),('BLOM','Bloom Ventures','Consumer',59,'✿'),
    ('TIDE','Tide Logistics','Transport',93,'♧'),('FROST','Frost Foods','Consumer',86,'❅'),
    ('KITE','Kite Networks','Technology',135,'⌘'),('MINT','Mint Services','Services',110,'◉'),
    ('ECHO','Echo Audio','Technology',75,'♪'),('CIRR','Cirrus Air','Transport',130,'☁'),
    ('OILS','Oil Barrel Index','Energy commodity',104,'◉'),('BRNT','Brent Barrel Index','Energy commodity',108,'◉'),
    ('NGAS','Natural Gas Index','Energy commodity',49,'ϟ'),('URAN','Uranium Index','Energy commodity',83,'◆'),
    ('XAUS','Gold Bullion Index','Metals commodity',153,'◇'),('XAGS','Silver Bullion Index','Metals commodity',65,'◇'),
    ('COPR','Copper Index','Metals commodity',96,'◇'),('PLAT','Platinum Index','Metals commodity',117,'◇'),
    ('WHEA','Wheat Index','Agriculture commodity',71,'❧'),('CORN','Corn Index','Agriculture commodity',52,'❧'),
    ('COCO','Cocoa Index','Agriculture commodity',89,'❧'),('COFF','Coffee Index','Agriculture commodity',61,'❧'),
    ('EURX','EUR/USD Index','FX index',100,'¤'),('GBPX','GBP/USD Index','FX index',109,'¤'),
    ('JPYX','USD/JPY Index','FX index',95,'¤'),('CHFX','USD/CHF Index','FX index',101,'¤'),
    ('CADX','USD/CAD Index','FX index',97,'¤'),('AUDX','AUD/USD Index','FX index',93,'¤'),
)
REFERENCE_CODES = {
    'OILS':'EIA:WTI','BRNT':'EIA:BRENT','NGAS':'EIA:NATGAS',
    'XAUS':'METALS:XAU','XAGS':'METALS:XAG','COPR':'METALS:COPPER','PLAT':'METALS:XPT',
    'EURX':'ECB:EURUSD','GBPX':'ECB:GBPUSD','JPYX':'ECB:USDJPY',
    'CHFX':'ECB:USDCHF','CADX':'ECB:USDCAD','AUDX':'ECB:AUDUSD',
}
STRATEGIES = (
    'market_maker','spread_scalper','liquidity_taker','pairs_trader',
    'momentum','trend_follower','breakout','contrarian',
    'value','growth','dividend','earnings',
    'commodity_hedger','currency_trader','sector_rotation','news_reactor',
    'mean_reversion','volatility_manager','portfolio_rebalancer','retail_random',
)
BOT_COUNT = 200
BOT_ORDERS_PER_AUCTION = 20
BOT_SEED_CREDITS = 30000  # Practice only; never transferable to Tavi Gold.


def reference_class(sector):
    if sector=='FX index':return 'fx'
    if 'commodity' in sector:return 'commodity'
    return 'equity'


def deterministic_number(*parts):
    return int.from_bytes(hashlib.sha256(':'.join(map(str,parts)).encode()).digest()[:8], 'big')


def maximum_fill_plan(buys, sells, price):
    """Max-flow matching with no self matches; all orders are nonnegative/finite."""
    bids=[dict(o) for o in buys if o['limit_price']>=price and o['remaining']>0]
    asks=[dict(o) for o in sells if o['limit_price']<=price and o['remaining']>0]
    if not bids or not asks:return []
    bn,sn=len(bids),len(asks);sink=1+bn+sn
    edges=[[] for _ in range(sink+1)]
    def add(u,v,cap):
        e={'to':v,'rev':len(edges[v]),'cap':cap,'original':cap}
        r={'to':u,'rev':len(edges[u]),'cap':0,'original':0}
        edges[u].append(e);edges[v].append(r)
        return e
    for i,b in enumerate(bids):add(0,1+i,b['remaining'])
    for j,s in enumerate(asks):add(1+bn+j,sink,s['remaining'])
    pair_edges=[]
    for i,b in enumerate(bids):
        for j,s in enumerate(asks):
            if b['player_id']!=s['player_id']:
                e=add(1+i,1+bn+j,min(b['remaining'],s['remaining']))
                pair_edges.append((i,j,e))
    while True:
        level=[-1]*(sink+1);level[0]=0;queue=[0]
        for u in queue:
            for e in edges[u]:
                if e['cap']>0 and level[e['to']]<0:
                    level[e['to']]=level[u]+1;queue.append(e['to'])
        if level[sink]<0:break
        cursor=[0]*(sink+1)
        def push(u,cap):
            if u==sink:return cap
            while cursor[u]<len(edges[u]):
                e=edges[u][cursor[u]]
                if e['cap']>0 and level[e['to']]==level[u]+1:
                    q=push(e['to'],min(cap,e['cap']))
                    if q:
                        e['cap']-=q;edges[e['to']][e['rev']]['cap']+=q
                        return q
                cursor[u]+=1
            return 0
        while push(0,10**9):pass
    return [(bids[i],asks[j],e['original']-e['cap']) for i,j,e in pair_edges if e['cap']<e['original']]


def choose_peer_auction(orders, opening):
    buys=sorted((dict(o) for o in orders if o['side']=='buy'), key=lambda o:(-o['limit_price'],o['created'],o['id']))
    sells=sorted((dict(o) for o in orders if o['side']=='sell'), key=lambda o:(o['limit_price'],o['created'],o['id']))
    if not buys or not sells:return opening,[]
    # Circuit breaker applies to executed prices, not to permissible order limits.
    max_move=max(1,opening*12//100)
    candidates={opening}
    candidates.update(o['limit_price'] for o in buys+sells if max(1,opening-max_move)<=o['limit_price']<=opening+max_move)
    best=[];best_price=opening
    for candidate in sorted(candidates):
        if abs(candidate-opening)>max_move:continue
        matched=maximum_fill_plan(buys,sells,candidate)
        qty=sum(q for _,_,q in matched);old=sum(q for _,_,q in best)
        if qty>old or (qty==old and (abs(candidate-opening),candidate)<(abs(best_price-opening),best_price)):
            best,best_price=matched,candidate
    return best_price,best


def bot_intent(strategy, *, price, reference, shares, available, period, bot_id, symbol):
    """Deterministic strategy variants: signals affect behavior, not balances."""
    rand=deterministic_number('intent',period,bot_id,symbol)
    index=STRATEGIES.index(strategy)
    trend=(rand//7)%17-8
    discount=(reference-price)*100//max(1,reference)
    signal=trend
    if index in (4,5,6,11,15):signal+=4 if price>=reference else -3
    if index in (7,8,16):signal+=max(-8,min(8,discount*2))
    if index in (12,13,14):signal+=(rand//59)%7-3
    if index in (0,1,2,3):signal+=(rand//83)%5-2
    if index in (17,18):signal-=4 if available<price*5 else 0
    if index==19:signal=(rand//103)%19-9
    side='buy' if signal>=0 else 'sell'
    if side=='sell' and shares==0:side='buy'
    qty=1+(rand//137)%4
    if side=='sell':qty=min(qty,shares)
    if side=='buy':qty=min(qty,max(0,available//(price+max(1,price//100)+4)))
    if qty<=0:return None
    spread=max(1,price//33)
    limit=max(1,min(10000,price+(spread if side=='buy' else -spread)))
    return (side,int(qty),int(limit))
