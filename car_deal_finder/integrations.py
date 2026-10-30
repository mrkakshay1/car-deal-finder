"""Authorized external inventory and manually provided Marketplace text only."""
import math
import re
from datetime import date
from functools import lru_cache
import requests
from engine import COLUMNS

@lru_cache(maxsize=2048)
def zip_coordinates(zip_code):
    code = str(zip_code).strip().split('.')[0].zfill(5)
    if not re.fullmatch(r'\d{5}', code):
        return None
    try:
        response = requests.get(f'https://api.zippopotam.us/us/{code}', timeout=6)
        response.raise_for_status()
        place = response.json()['places'][0]
        return float(place['latitude']), float(place['longitude'])
    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None

def distance_miles(a, b):
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2-lat1, lon2-lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 3958.7613*2*math.asin(min(1, math.sqrt(h)))

def attach_distance(df, origin_zip, radius):
    """Remove unknown-location listings rather than implying they are nearby."""
    center = zip_coordinates(origin_zip)
    if center is None:
        raise ValueError('Search ZIP could not be resolved. Check ZIP or internet connection.')
    out = df.copy()
    coords = {z: zip_coordinates(z) for z in out['zip_code'].astype(str).unique()}
    out['distance_miles'] = out['zip_code'].astype(str).map(
        lambda z: round(distance_miles(center,coords[z]),1) if coords.get(z) else float('nan'))
    missing = int(out.distance_miles.isna().sum())
    return out[out.distance_miles <= radius].copy(), missing

def normalize_marketcheck(item, kind):
    build = item.get('build') or {}
    if not isinstance(build,dict): build={}
    dealer = item.get('dealer') or {}
    if not isinstance(dealer,dict): dealer={}
    source = item.get('source') or item.get('source_name') or item.get('seller_type') or ('MarketCheck dealer' if kind=='dealer' else 'MarketCheck private seller')
    if isinstance(source,dict): source=source.get('name','MarketCheck')
    source = str(source)
    if 'facebook' not in source.lower():
        source = f'MarketCheck {kind} ({source})'
    # Do not label provider listings "Facebook" merely because their sources are unverified.
    elif not (str(item.get('vdp_url') or item.get('listing_url') or item.get('url') or '')).lower().find('facebook.com')>=0:
        source = f'MarketCheck {kind} (source unverified)'
    return dict(source=source,year=item.get('year') or build.get('year'),make=item.get('make') or build.get('make',''),
        model=item.get('model') or build.get('model',''),trim=item.get('trim') or build.get('trim',''),
        mileage=item.get('miles') or item.get('mileage') or 0,price=item.get('price'),
        zip_code=str(item.get('zip') or dealer.get('zip') or ''),
        title_status='',description=item.get('seller_comments') or item.get('description') or '',
        url=item.get('vdp_url') or item.get('listing_url') or item.get('url') or '',date_seen=date.today().isoformat())

def fetch_marketcheck(api_key, zip_code, radius, max_price, make='', model='', kind='dealer', rows=50, pages=1):
    if not api_key.strip(): raise ValueError('MarketCheck API key is required.')
    endpoint = 'fsbo/active' if kind=='private' else 'active'
    url = f'https://api.marketcheck.com/v2/search/car/{endpoint}'
    rows = min(max(int(rows),1),50)
    pages = min(max(int(pages),1),5)
    result=[]
    for page in range(pages):
        params={'api_key':api_key.strip(),'zip':zip_code,'radius':int(radius),'price_range':f'1-{int(max_price)}',
                'car_type':'used','rows':rows,'start':page*rows,'country':'us'}
        if make.strip(): params['make']=make.strip()
        if model.strip(): params['model']=model.strip()
        response = requests.get(url,params=params,headers={'Accept':'application/json'},timeout=25)
        response.raise_for_status()
        payload=response.json()
        if isinstance(payload,dict) and (payload.get('error') or payload.get('errors')):
            raise ValueError(str(payload.get('error') or payload.get('errors')))
        items=payload.get('listings',[]) if isinstance(payload,dict) else []
        if not isinstance(items,list): raise ValueError('Unexpected MarketCheck response format.')
        result.extend(normalize_marketcheck(item,kind) for item in items if isinstance(item,dict))
        if len(items)<rows: break
    return result

def parse_facebook_text(raw, default_zip=''):
    """Explicit paste workflow, never requests a Facebook URL."""
    text=raw.strip()
    if not text: raise ValueError('Paste a seller listing description first.')
    def grab(pattern):
        match=re.search(pattern,text,re.IGNORECASE)
        return match.group(1).strip() if match else ''
    heading = grab(r'(?m)^\s*((?:19|20)\d{2})\s+([A-Za-z][\w-]*)\s+([A-Za-z0-9][\w-]*)')
    car = re.search(r'\b((?:19|20)\d{2})\s+([A-Za-z][\w-]*)\s+([A-Za-z0-9][\w-]*)',text)
    if not car: raise ValueError('Could not find year, make and model. Put "2018 Honda Civic" at the beginning.')
    price = grab(r'(?:\$|price\s*[:=]\s*\$?)\s*([\d,]+(?:\.\d{2})?)')
    miles = grab(r'([\d,]+)\s*(?:miles|mi\b)') or grab(r'(?:mileage|odometer)\s*[:=]\s*([\d,]+)')
    if not price or not miles: raise ValueError('Include a price like $12000 and mileage like 75000 miles.')
    url = grab(r'(https?://(?:www\.|m\.)?facebook\.com/(?:marketplace/)?[^\s<>]+)')
    z = grab(r'\bZIP\s*[:=]\s*(\d{5})\b') or default_zip
    trim = grab(r'\btrim\s*[:=]\s*([^\n]+)')
    title = grab(r'\btitle\s*[:=]\s*(clean|rebuilt|salvage|unknown)\b')
    return dict(source='Facebook Marketplace',year=int(car.group(1)),make=car.group(2),model=car.group(3),trim=trim,
      mileage=int(miles.replace(',','')),price=float(price.replace(',','')),zip_code=z,title_status=title,
      description=text,url=url.rstrip('.,)'),date_seen=date.today().isoformat())
