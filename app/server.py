"""Local prototype HTTP adapter. Production deployment requires auth/moderation/rights review."""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import threading
import time
from collections import defaultdict, deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app.image_provider import ImageProviderError, generate
from app.picsy import demo_three_person
from app.store import Store, DomainError

ROOT=Path(__file__).resolve().parent.parent
WEB=ROOT/'web'
DB=os.environ.get('ZOKU_DB', str(ROOT/'data'/'zokuzoku.sqlite'))
MEDIA=Path(os.environ.get('ZOKU_MEDIA_DIR', str(ROOT/'data'/'media'))).resolve()
STORE=Store(DB)
MEDIA.mkdir(parents=True,exist_ok=True)
DEMO=os.environ.get('ZOKU_DEMO_MODE','1')=='1'
IMAGE_HOURLY_LIMIT=int(os.environ.get('ZOKU_IMAGE_HOURLY_LIMIT','3'))
IMAGE_TOTAL_LIMIT=int(os.environ.get('ZOKU_IMAGE_TOTAL_LIMIT','50'))
rate_lock=threading.Lock()
requests_by_actor=defaultdict(deque)
image_total=0
LOGGER=logging.getLogger('zokuzoku')
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')


def limited(key: str, limit: int, period: int) -> bool:
    t=time.monotonic()
    with rate_lock:
        q=requests_by_actor[key]
        while q and q[0]<t-period:
            q.popleft()
        if len(q)>=limit:
            return True
        q.append(t)
    return False


class Handler(BaseHTTPRequestHandler):
    server_version='ZokuZokuMVP/0.1'
    protocol_version='HTTP/1.1'

    def log_message(self, fmt, *args):
        LOGGER.info('%s - %s',self.address_string(),fmt % args)

    def _send(self, status, data, content_type='application/json; charset=utf-8'):
        b=(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode() if not isinstance(data,bytes) else data)
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(b)))
        self.send_header('Cache-Control','no-store' if content_type.startswith('application/json') else 'public, max-age=300')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(b)

    def _error(self, status, message):
        self._send(status,{'error':message})

    def _actor(self):
        if not DEMO: raise DomainError('Demo identity disabled; production auth is not configured',503)
        actor=self.headers.get('X-Demo-User','a')
        if actor not in ('a','b','c','d'): raise DomainError('Invalid demo user',403)
        return actor

    def _origin(self):
        origin=self.headers.get('Origin')
        if origin and origin != f'http://{self.headers.get("Host","")}' and origin != f'https://{self.headers.get("Host","")}':
            raise DomainError('Cross-origin writes are disabled',403)

    def _body(self):
        typ=self.headers.get('Content-Type','').split(';')[0].strip()
        if typ!='application/json':raise DomainError('Content-Type must be application/json',415)
        try: size=int(self.headers.get('Content-Length','0'))
        except ValueError:raise DomainError('Invalid content length')
        if size<=0 or size>16*1024:raise DomainError('Request body exceeds 16KB',413)
        try: value=json.loads(self.rfile.read(size))
        except (ValueError,UnicodeDecodeError):raise DomainError('Malformed JSON')
        if not isinstance(value,dict): raise DomainError('Expected JSON object')
        return value

    def do_GET(self):
        try:
            path=urlsplit(self.path).path
            if path in ('/','/index.html'):return self._static('index.html')
            if path.startswith('/static/'):
                name=path.removeprefix('/static/')
                if name not in ('app.js','styles.css'):return self._error(404,'Not found')
                return self._static(name)
            if path.startswith('/media/'):
                name=path.removeprefix('/media/')
                if not re.fullmatch(r'idea-[a-f0-9]{16}\.png',name):return self._error(404,'Not found')
                p=MEDIA/name
                if not p.is_file():return self._error(404,'Not found')
                return self._send(200,p.read_bytes(),'image/png')
            if path=='/health':return self._send(200,{'status':'ok','demo':DEMO})
            if path=='/api/ideas':return self._send(200,STORE.list_ideas(self.headers.get('X-Demo-User','a')))
            if path=='/api/events':return self._send(200,{'seq':STORE.latest_seq()})
            if path=='/api/insights':return self._send(200,STORE.insights())
            if path=='/api/picsy':return self._send(200,demo_three_person())
            m=re.fullmatch(r'/api/ideas/([a-z0-9-]+)/comments',path)
            if m:return self._send(200,{'comments':STORE.comments(m[1])})
            self._error(404,'Not found')
        except DomainError as e:self._error(e.status,str(e))
        except Exception:
            LOGGER.exception('GET failed')
            self._error(500,'Internal server error')

    def _static(self,name):
        p=WEB/name
        ctype='text/html; charset=utf-8' if name.endswith('.html') else 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8'
        self._send(200,p.read_bytes(),ctype)

    def do_POST(self):
        global image_total
        path=urlsplit(self.path).path
        try:
            self._origin()
            actor=self._actor()
            if limited('write:'+actor,80,60):raise DomainError('Too many writes, slow down',429)
            body=self._body()
            if path=='/api/ideas':return self._send(201,STORE.create_idea(actor,body))
            m=re.fullmatch(r'/api/ideas/([a-z0-9-]+)/(like|pledge|comment|generate)',path)
            if not m:raise DomainError('Unknown endpoint',404)
            idea_id,action=m.groups()
            if action=='like':return self._send(200,STORE.like(actor,idea_id))
            if action=='pledge':return self._send(200,STORE.pledge(actor,idea_id,body.get('points')))
            if action=='comment':return self._send(201,STORE.comment(actor,idea_id,str(body.get('body',''))))
            if action=='generate':
                if not os.environ.get('OPENAI_API_KEY'):
                    raise DomainError('Image generation is not configured. Set OPENAI_API_KEY on the server.',503)
                if limited('image:'+actor,IMAGE_HOURLY_LIMIT,3600):
                    raise DomainError('Hourly image-generation limit reached',429)
                with rate_lock:
                    if image_total>=IMAGE_TOTAL_LIMIT:
                        raise DomainError('Server image budget reached',429)
                    image_total+=1
                idea=STORE.begin_image(idea_id,actor)
                parent_image=None
                if idea.get('parent_id'):
                    all_ideas=STORE.list_ideas(actor)['ideas']
                    parent=next((i for i in all_ideas if i['id']==idea['parent_id']),None)
                    if parent and parent['image_path']:
                        possible=MEDIA/Path(parent['image_path']).name
                        if possible.is_file():parent_image=possible
                try:
                    content=generate(idea['prompt'],parent_image)
                    target=MEDIA/f'{idea_id}.png'
                    temporary=MEDIA/f'{idea_id}.tmp'
                    temporary.write_bytes(content)
                    os.replace(temporary,target)
                    STORE.finish_image(idea_id,'/media/'+target.name)
                except ImageProviderError as e:
                    STORE.fail_image(idea_id,str(e))
                    raise DomainError(str(e),502)
                except Exception:
                    STORE.fail_image(idea_id,'unexpected provider failure')
                    raise
                return self._send(201,{'image_path':'/media/'+target.name})
        except DomainError as e:self._error(e.status,str(e))
        except BrokenPipeError:pass
        except Exception:
            LOGGER.exception('POST failed')
            self._error(500,'Internal server error')


def run(host=None, port=None):
    host=host or os.environ.get('ZOKU_HOST','127.0.0.1')
    port=port or int(os.environ.get('PORT','8000'))
    server=ThreadingHTTPServer((host,port),Handler)
    LOGGER.info('ZokuZoku listening on http://%s:%d — DEMO_MODE=%s',host,port,DEMO)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':run()
