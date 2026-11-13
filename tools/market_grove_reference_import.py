"""Operator-only Market Grove reference importer (no browser credentials).

Manual/default mode prints validated observations. --apply posts to separately
scoped market:reference endpoint. ECB source is an opt-in external data fetch.
This utility is never invoked from the unprivileged Atrium web client.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ECB_URL = ('https://data-api.ecb.europa.eu/service/data/EXR/'
           'D.USD+GBP+JPY+CHF+CAD+AUD.EUR.SP00.A?format=csvdata&lastNObservations=1')
ALLOWED = {'EURX','GBPX','JPYX','CHFX','CADX','AUDX','OILS','BRNT','NGAS','XAUS','XAGS','COPR','PLAT'}


def parse_ecb_csv(content: str) -> list[dict]:
    reader=csv.DictReader(StringIO(content))
    if not reader.fieldnames or not {'CURRENCY','OBS_VALUE','TIME_PERIOD'}<=set(reader.fieldnames):
        raise ValueError('Missing required ECB observation columns')
    rates={}
    for row in reader:
        ccy=row['CURRENCY']
        if ccy not in {'USD','GBP','JPY','CHF','CAD','AUD'}:continue
        val=Decimal(row['OBS_VALUE']);observed=date.fromisoformat(row['TIME_PERIOD'])
        if not val.is_finite() or not 0<val<=Decimal('10000000'):raise ValueError('Invalid ECB observation')
        existing=rates.get(ccy)
        if existing is None or observed>existing[1]:rates[ccy]=(val,observed)
    if len(rates)!=6:raise ValueError('ECB response omitted one or more required currencies')
    dates={v[1] for v in rates.values()}
    if len(dates)!=1:raise ValueError('ECB observations do not share one publication date')
    obs=next(iter(dates))
    usd,gbp,jpy,chf,cad,aud=(rates[x][0] for x in ('USD','GBP','JPY','CHF','CAD','AUD'))
    derivations={'EURX':usd,'GBPX':usd/gbp,'JPYX':jpy/usd,
                 'CHFX':chf/usd,'CADX':cad/usd,'AUDX':usd/aud}
    stamp=int(datetime.combine(obs,time(12),tzinfo=timezone.utc).timestamp())
    return [{'symbol':sym,'source':'ecb-daily','observation':str(val.quantize(Decimal('0.00000001'),rounding=ROUND_HALF_UP)),
             'observedAt':stamp,'requestId':f'ecb_{obs.isoformat()}_{sym}'} for sym,val in derivations.items()]


def fetch_ecb():
    request=Request(ECB_URL,headers={'Accept':'text/csv','User-Agent':'AtriumMarketGrove/0.5.84 (operator importer)'})
    with urlopen(request,timeout=15) as response:
        if response.geturl().split('/')[2] != 'data-api.ecb.europa.eu':raise ValueError('Unexpected ECB redirect')
        raw=response.read(256*1024+1)
    if len(raw)>256*1024:raise ValueError('ECB response too large')
    return parse_ecb_csv(raw.decode('utf-8-sig'))


def validate(items):
    if not isinstance(items,list) or not 1<=len(items)<=20:raise ValueError('Expected 1..20 observations')
    for body in items:
        if not isinstance(body,dict) or set(body)!={'symbol','source','observation','observedAt','requestId'}:
            raise ValueError('Invalid observation fields')
        if body['symbol'] not in ALLOWED or body['source'] not in {'ecb-daily','eia-daily','licensed-metals'}:
            raise ValueError('Invalid reference source')
        if not isinstance(body['observation'],str) or not re.fullmatch(r'[0-9]{1,8}(?:\.[0-9]{1,8})?',body['observation']):
            raise ValueError('Invalid observation precision')
        if type(body['observedAt']) is not int or body['observedAt']<1 or not isinstance(body['requestId'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',body['requestId']):
            raise ValueError('Invalid timestamp/request identifier')
    return items


def market_base_url(url):
    u=urlparse(url)
    if u.username or u.password or u.params or u.query or u.fragment or u.scheme not in ('https','http'):
        raise ValueError('Invalid market URL')
    if u.scheme=='http' and u.hostname not in ('localhost','127.0.0.1'):
        raise ValueError('Production market URL must be HTTPS')
    if not re.fullmatch(r'/looprd/(?:[a-z][a-z0-9-]{0,47}/){0,8}market-grove/v[1-9][0-9]*/?',u.path):
        raise ValueError('Expected scoped Market Grove child API base URL')
    return url.rstrip('/')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--ecb',action='store_true',help='Fetch ECB latest daily rate references')
    source.add_argument('--file',type=Path,help='Operator-vetted JSON observations')
    parser.add_argument('--apply',action='store_true',help='Send to trusted reference service; default prints only')
    parser.add_argument('--base-url',help='HTTPS Market Grove LoopRD child root')
    args=parser.parse_args()
    items=validate(fetch_ecb() if args.ecb else json.loads(args.file.read_text(encoding='utf-8')))
    if not args.apply:
        print(json.dumps(items,indent=2));return
    if not args.base_url:parser.error('--apply requires --base-url')
    base=market_base_url(args.base_url)
    token=os.environ.get('MARKET_GROVE_REFERENCE_TOKEN','')
    if not token:parser.error('MARKET_GROVE_REFERENCE_TOKEN must be provided only through the operator environment')
    for item in items:
        request=Request(base+'/market/reference/observation',method='POST',
                        headers={'Content-Type':'application/json','Authorization':'Bearer '+token},
                        data=json.dumps(item).encode('utf-8'))
        with urlopen(request,timeout=20) as response:
            print(response.read(2048).decode('utf-8'))

if __name__=='__main__':main()
