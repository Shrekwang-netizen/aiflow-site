import unittest, json, sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
from copy import deepcopy
from datetime import date,datetime,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build import validate,eligible,lottery_records
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.feed_ids=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if 'feed-item' in a.get('class','').split():self.feed_ids.append(a['data-id'])
        for k in ('href','src'):
            if a.get(k):self.links.append(a[k])
class PublicationTests(unittest.TestCase):
    def setUp(self):self.records=json.loads((ROOT/'data/records.json').read_text())
    def test_records_valid(self):validate(self.records)
    def test_reject_duplicate(self):
        with self.assertRaises(AssertionError):validate(self.records+[self.records[0]])
    def test_profile_link_cannot_verify(self):
        r=deepcopy(next(r for r in self.records if r['status']=='primary'));r['sources'][0]['url']='https://x.com/example'
        with self.assertRaises(AssertionError):validate([r])
    def test_rumor_not_checked(self):
        r=deepcopy(next(r for r in self.records if r['status']=='primary'));r['type']='rumor'
        with self.assertRaises(AssertionError):validate([r])
    def test_context_not_talent_news(self):
        r=deepcopy(next(r for r in self.records if r['status']=='primary'));r['scope']='context';self.assertFalse(eligible(r))
    def test_home_news_only_checked(self):
        parser=Links();parser.feed((ROOT/'index.html').read_text())
        expected=sorted((r for r in self.records if eligible(r)),key=lambda r:(r['date'],r['id']),reverse=True)[:9]
        self.assertEqual(parser.feed_ids,[r['id'] for r in expected])
    def test_random_only_recent_checked(self):
        as_of=datetime.fromisoformat(json.loads((ROOT/'data/monitor.json').read_text())['checked_at']).date()
        cutoff=as_of-timedelta(days=7)
        pool=json.loads((ROOT/'assets/data/random.json').read_text())
        expected={r['id'] for r in self.records if eligible(r) and cutoff<=date.fromisoformat(r['date'])<=as_of}
        self.assertEqual({r['id'] for r in pool},expected)
    def test_lottery_excludes_unverified_and_out_of_window_records(self):
        base={'status':'primary','scope':'talent','type':'join','date':'2026-11-05'}
        cases=[('primary',{}),('reported',{'status':'reported'}),
               ('cutoff',{'date':'2026-10-29'}),('too_old',{'date':'2026-10-28'}),
               ('future',{'date':'2026-11-06'}),('unreviewed',{'status':'unreviewed'}),
               ('lead',{'status':'lead'}),('context',{'scope':'context'}),
               ('rumor',{'type':'rumor'}),('opinion',{'type':'opinion'}),
               ('sentiment',{'type':'sentiment'})]
        records=[dict(base,id=label,**changes) for label,changes in cases]
        self.assertEqual({r['id'] for r in lottery_records(records,date(2026,11,5))},
                         {'primary','reported','cutoff'})
    def test_generated_local_links(self):
        missing=[]
        for p in ROOT.rglob('*.html'):
            if '.git' in p.parts:continue
            parser=Links();parser.feed(p.read_text())
            for url in parser.links:
                u=urlsplit(url)
                if u.scheme or u.netloc or not u.path:continue
                if not (p.parent/unquote(u.path)).resolve().exists():missing.append((str(p.relative_to(ROOT)),url))
        self.assertEqual(missing,[])
    def test_legacy_articles_preserved(self):
        for r in self.records:self.assertTrue((ROOT/'item'/f'{r["id"]}.html').exists())
    def test_watch_handles_unique(self):
        a=json.loads((ROOT/'data/x-watchlist.json').read_text())['accounts'];self.assertEqual(len(a),len({x['handle'].lower() for x in a}))
if __name__=='__main__':unittest.main()
