#!/usr/bin/env python3
"""Offline playlist metadata engine v1.0. Python 3.9+, standard library only."""
import argparse
import collections
import html
import json
import re
import unicodedata
from pathlib import Path

COUNTRIES = {x.upper(): x for x in 'de uk us nl it fr pl gr tr pt ch es ro ca rs be al cz hr cy bg hk mx il mt nz au pk fi br ba hu id my at lv sg ph ae sa ru si se dk lt ie mk no'.split()}
COUNTRIES.update({'GB':'uk','USA':'us','CA EN':'ca','CA FR':'ca','ARG':'ar','COL':'co','CHL':'cl','UKR':'ua','ECU':'ec','AZE':'az'})
REGIONAL = {'AR':'arabic','ASIA':'asia','AFR':'africa','LAT':'latin_america','LATIN':'latin_america'}
QUALITY = re.compile(r'(?<!\w)(?:FHD|UHD|HD|SD|4K|8K|HEVC|H[ .]?265|H[ .]?264|1080[PI]|720P|2160P|576P|480P)(?!\w)',re.I)
ATTR = re.compile(r'([\w-]+)="([^"]*)"')
SECRET = re.compile(r'https?://|\b(?:bearer|token|password|username|mac)\s*[:=]|(?:[0-9a-f]{2}:){5}[0-9a-f]{2}|(?:[\w-]+\.)+(?:com|net|org|tv|io|xyz|cc|live|info|me|co|uk)(?=[:/\s]|$)',re.I)

def safe(s):
    s = html.unescape(str(s)).strip()
    return '[redacted]' if SECRET.search(s) else s

def prefix(s):
    m = re.match(r'^\s*([^┃|:]{1,24})\s*[┃|:]\s*(.*)$',s)
    if m: return m.group(1).strip().upper(),m.group(2).strip()
    m = re.match(r'^([A-Z]{2,5}(?: EN| FR)?)\s+-\s+(.*)$',s)
    return (m.group(1),m.group(2)) if m else ('',s)

def record(attrs, display):
    name = safe(attrs.get('tvg-name') or display)
    group = safe(re.sub(r'^\s*\[[^]]+\]\s*','',attrs.get('group-title','')))
    cid = safe(attrs.get('tvg-id',''))
    np, body = prefix(name); gp,_ = prefix(group)
    if not gp and group.upper() in COUNTRIES: gp=group.upper()
    evidence = {}
    for field,p in [('name_prefix',np),('group_prefix',gp)]:
        if p in COUNTRIES: evidence[field]=COUNTRIES[p]
    suffix = re.search(r'\[([^]]+)\]\s*$',body)
    if suffix and suffix.group(1).upper() in COUNTRIES:
        evidence['name_suffix']=COUNTRIES[suffix.group(1).upper()]; body=body[:suffix.start()].strip()
    if np not in COUNTRIES and np not in REGIONAL and np not in {'UCL','PPV','SPORTS','F1 TV','MOTOGP','CANAL+'}: body=name
    regions=set(evidence.values()); region=next(iter(regions)) if len(regions)==1 else None
    status='conflict' if len(regions)>1 else 'identified' if region else 'unknown'
    qualities=list(dict.fromkeys(x.group().upper() for x in QUALITY.finditer(body)))
    clean=QUALITY.sub(' ',body); clean=re.sub(r'\[\s*\]|\(\s*\)',' ',clean); clean=' '.join(clean.split()).strip(' -|┃')
    heading=bool(re.search(r'☰{2,}|UPDATE YOUR PLAYLIST|^[═━─*]{3,}',name,re.I))
    event=bool(re.search(r'\b(?:PPV|EVENTS?|MATCHDAY)\b',name+' '+group,re.I) or np in {'UCL','F1 TV','MOTOGP'})
    kind='category_heading' if heading else 'event_review' if event else 'regular'
    key=' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',clean).casefold()))
    return {'tvg_id':cid,'original_name':name,'display_name':safe(display),'group':group,'matching_name':clean,'matching_key':key,'region':region,'region_status':status,'region_evidence':evidence,'regional_group':REGIONAL.get(np) or REGIONAL.get(gp),'quality':qualities,'kind':kind}

def parse(path):
    for line in path.open(encoding='utf-8-sig',errors='replace'):
        if not line.startswith('#EXTINF:'): continue
        # Locate first comma outside quoted attributes.
        m=re.match(r'^#EXTINF:((?:[^",]|"[^"]*")*),(.*)$',line.rstrip('\r\n'))
        if m: yield record(dict(ATTR.findall(m.group(1))),m.group(2))

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('playlist',nargs='?',default='Mac_playlist.m3u'); p.add_argument('--output-dir',default='metadata'); a=p.parse_args()
    rows=list(parse(Path(a.playlist))); ids=collections.Counter(r['tvg_id'] for r in rows if r['tvg_id']); identities=collections.Counter((r['region'],r['matching_key']) for r in rows if r['region'] and r['matching_key'] and r['kind']=='regular')
    for r in rows:
        r['duplicate_id']=ids[r['tvg_id']]>1; r['identity_candidate_count']=identities[(r['region'],r['matching_key'])]
    report={'version':'1.0','entries':len(rows),'unique_ids':len(ids),'missing_ids':sum(not r['tvg_id'] for r in rows),'duplicate_ids':{k:v for k,v in ids.items() if v>1},'region_status':dict(collections.Counter(r['region_status'] for r in rows)),'regions':dict(collections.Counter(r['region'] or 'unknown' for r in rows)),'kinds':dict(collections.Counter(r['kind'] for r in rows)),'quality_labelled':sum(bool(r['quality']) for r in rows),'review_entries':sum(r['region_status']!='identified' or r['kind']!='regular' for r in rows)}
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    for filename,data in [('channel_catalogue.json',rows),('metadata_report.json',report)]:
        (out/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
