import unittest, json, sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build import validate,eligible
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
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
    def test_random_only_checked(self):
        pool=json.loads((ROOT/'assets/data/random.json').read_text());expected={r['id'] for r in self.records if eligible(r)}
        self.assertEqual({r['id'] for r in pool},expected)
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
