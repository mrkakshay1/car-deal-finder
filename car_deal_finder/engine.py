"""Transparent car-market comparison engine. No site scraping required."""
import re
from dataclasses import dataclass
import pandas as pd
import numpy as np

COLUMNS = ['source','year','make','model','trim','mileage','price','zip_code','title_status','description','url','date_seen']
RISK_RULES = [
    (r'\b(salvage|rebuilt|reconstructed|flood title|branded title)\b', 'Branded/salvage title', 28),
    (r'\b(no title|lost title|title missing|bill of sale only)\b', 'Title documentation issue', 35),
    (r'\b(check engine|cel on|engine light)\b', 'Check-engine light', 14),
    (r'\b(overheat|head gasket|knocking|rod knock)\b', 'Potential serious engine issue', 28),
    (r'\b(transmission slip|transmission issue|needs transmission|won.t shift)\b', 'Transmission concern', 26),
    (r'\b(not running|doesn.t run|won.t start|mechanic special)\b', 'Vehicle may not run', 25),
    (r'\b(as.is|as is|needs work|needs tlc|project car)\b', 'Condition uncertainty', 7),
    (r'\b(deposit first|shipping only|gift card|wire transfer)\b', 'Potential payment scam signal', 30),
]

def clean_data(df):
    df = df.copy()
    for col in COLUMNS:
        if col not in df: df[col] = ''
    for col in ['make','model','trim','source','title_status','description','url','zip_code','date_seen']:
        df[col] = df[col].fillna('').astype(str).str.strip()
    for col in ['year','mileage','price']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['year','mileage','price'])
    df = df[(df.price > 0) & (df.mileage >= 0) & df.year.between(1980, 2030)].copy()
    df['year'] = df.year.astype(int)
    df['make_key'] = df.make.str.casefold()
    df['model_key'] = df.model.str.casefold()
    df['source_key'] = df.source.str.casefold()
    has_url = df['url'].str.startswith(('http://','https://'))
    df = pd.concat([df[~has_url], df[has_url].drop_duplicates(subset=['url'], keep='last')]).sort_index()
    return df.reset_index(drop=True)

def flags(row):
    text = (str(row.get('description','')) + ' ' + str(row.get('title_status',''))).lower()
    out, penalty = [], 0
    for pattern, label, points in RISK_RULES:
        if re.search(pattern, text):
            out.append(label); penalty += points
    if not str(row.get('title_status','')).strip():
        out.append('Title status unverified'); penalty += 8
    if not str(row.get('url','')).startswith(('http://','https://')):
        out.append('No listing link provided'); penalty += 4
    return out, min(85, penalty)

def calculate(df, focus='Facebook Marketplace', min_comps=2, year_tolerance=2, miles_tolerance=35000, trim_match=False, facebook_weight=0.75):
    """Compare against separate same make/model rows, adjust each comp for mileage/year.
    A comparable's adjusted price = price + $0.055*(comp miles - target miles)
    + $850*(target year - comp year). These are configurable heuristics, not valuations.
    Facebook is weighted more heavily if Facebook comps exist.
    """
    df = clean_data(df)
    candidates = df[df.source_key.str.contains('facebook', na=False)] if focus == 'Facebook Marketplace' else df
    output = []
    for idx, car in candidates.iterrows():
        comps = df[(df.make_key == car.make_key) & (df.model_key == car.model_key) &
                   ((df.year-car.year).abs() <= year_tolerance) &
                   ((df.mileage-car.mileage).abs() <= miles_tolerance) & (df.index != idx)].copy()
        if trim_match and car['trim']:
            comps = comps[comps['trim'].str.casefold() == car['trim'].casefold()]
        # Avoid using same URL across sources as an independent comp
        if car['url']:
            comps = comps[comps.url != car['url']]
        if len(comps) < min_comps:
            continue
        comps['adjusted'] = comps.price + 0.055*(comps.mileage-car.mileage) + 850*(car.year-comps.year)
        comps = comps[comps.adjusted > 500]
        if len(comps) < min_comps: continue
        fb = comps[comps.source_key.str.contains('facebook')]
        other = comps[~comps.source_key.str.contains('facebook')]
        fb_median = float(fb.adjusted.median()) if len(fb) else np.nan
        other_median = float(other.adjusted.median()) if len(other) else np.nan
        if len(fb) and len(other):
            estimate = fb_median*facebook_weight + other_median*(1-facebook_weight)
        elif len(fb): estimate = fb_median
        else: estimate = other_median
        discount = (estimate-car.price)/estimate*100 if estimate else 0
        problems, penalty = flags(car)
        # Confidence reflects sample size; score incorporates some risk, but does not certify safety.
        confidence = min(100, 35+9*len(comps) + (8 if len(fb)>=2 else 0))
        deal_score = max(0, min(100, 50 + 1.6*discount - penalty*0.8))
        output.append({**{c:car[c] for c in COLUMNS}, 'estimated_market':round(estimate),
            'discount_dollars':round(estimate-car.price), 'discount_pct':round(discount,1),
            'deal_score':round(deal_score), 'confidence':round(confidence),
            'facebook_comps':len(fb), 'external_comps':len(other),
            'facebook_median':round(fb_median) if len(fb) else np.nan,
            'external_median':round(other_median) if len(other) else np.nan,
            'flags':'; '.join(problems) if problems else 'No text-based flags found',
            'comp_count':len(comps)})
    if not output: return pd.DataFrame()
    return pd.DataFrame(output).sort_values(['deal_score','discount_pct'],ascending=False).reset_index(drop=True)
