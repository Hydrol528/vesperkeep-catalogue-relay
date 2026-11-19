"""Staged public catalogue-only relay; never forwards Jellyfin or video traffic.
Use HTTPS termination when deployed. Provider control keys never enter Udon.
A scope label groups routing only; it is not proof of VRChat instance membership.
The read capability must be distributed only through the intended instance.
"""
import json,os,re,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from shared_catalogue import SharedCatalogues,ShareDenied
CAP=re.compile(r'^[A-Za-z0-9_-]{32}$')

class BoundedHTTPServer(ThreadingHTTPServer):
 daemon_threads=True
 def __init__(self,*args,**kwargs):
  self.slots=threading.BoundedSemaphore(24);super().__init__(*args,**kwargs)
 def process_request(self,request,address):
  if not self.slots.acquire(blocking=False):
   self.shutdown_request(request);return
  try:super().process_request(request,address)
  except Exception:self.slots.release();raise
 def process_request_thread(self,request,address):
  try:super().process_request_thread(request,address)
  finally:self.slots.release()

def server(address=('127.0.0.1',0),store=None):
 store=store or SharedCatalogues()
 class Handler(BaseHTTPRequestHandler):
  def setup(self):
   super().setup();self.connection.settimeout(10)
  def log_message(self,*args):pass # Capability URLs and provider controls are not logged.
  def send(self,status,value,kind='application/json'):
   data=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode()
   self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
  def route(self):
   parts=self.path.split('?')[0].strip('/').split('/')
   if len(parts) not in (2,3) or parts[0]!='shared' or not CAP.fullmatch(parts[1]):raise ShareDenied('Connection unavailable')
   if len(parts)==2:return parts[1],'posters' if 'image/' in self.headers.get('Accept','').lower() else 'catalogue'
   return parts[1],parts[2]
  def control(self):
   value=self.headers.get('Authorization','')
   return value[7:] if value.startswith('Bearer ') else ''
  def do_GET(self):
   try:
    assets={'/':('portal.html','text/html; charset=utf-8'),'/portal-logo.png':('portal-logo.png','image/png'),'/cinzel.ttf':('cinzel.ttf','font/ttf'),'/Cinzel-OFL.txt':('Cinzel-OFL.txt','text/plain; charset=utf-8')}
    if self.path in assets:
     name,kind=assets[self.path];self.send(200,(ROOT/name).read_bytes(),kind);return
    if self.path=='/health':self.send(200,{'service':'vesper-catalogue-relay','ready':True});return
    cap,action=self.route()
    # The scope is resolved from the capability record, not a viewer-supplied identity.
    with store._lock:
     record=store._current(cap);scope=record['instance']
    if action=='catalogue':self.send(200,store.read(cap,scope));return
    if action=='posters':self.send(200,store.read(cap,scope,'posters'),'image/png');return
    if action=='selection':self.send(200,{'index':store.take_selection(cap,self.control())});return
    raise ShareDenied('Connection unavailable')
   except ShareDenied:self.send(403,{'error':'Catalogue disconnected or access unavailable'})
   except (BrokenPipeError,ConnectionResetError):pass
  def do_PUT(self):
   try:
    cap,action=self.route()
    if action!='posters' or self.headers.get('Content-Type','').split(';')[0]!='image/png':raise ShareDenied('Invalid posters')
    length=int(self.headers.get('Content-Length','0'))
    if length<8 or length>8*1024*1024:raise ShareDenied('Invalid posters')
    # Authenticate before reading a potentially large upload.
    with store._lock:
     import secrets
     if not secrets.compare_digest(store._current(cap)['control'],self.control()):raise ShareDenied('Provider approval required')
    data=self.rfile.read(length)
    if len(data)!=length:raise ShareDenied('Incomplete posters')
    store.set_posters(cap,self.control(),data);self.send(200,{'updated':True})
   except (ShareDenied,ValueError,TypeError):self.send(403,{'error':'Poster update unavailable'})
   except (BrokenPipeError,ConnectionResetError):pass
  def do_POST(self):
   try:
    length=int(self.headers.get('Content-Length','0'))
    if length<1 or length>1024*1024:raise ShareDenied('Invalid request')
    body=json.loads(self.rfile.read(length))
    if not isinstance(body,dict):raise ShareDenied('Invalid request')
    if self.path=='/shared/publish':
     # One connection per publisher request. No sign-in, token, or server URL accepted here.
     if set(body)-{'provider','instance','catalogue'}:raise ShareDenied('Unexpected publication fields')
     provider=body.get('provider');instance=body.get('instance')
     if not isinstance(provider,str) or not isinstance(instance,str) or not 16<=len(provider)<=128 or not 16<=len(instance)<=128:raise ShareDenied('Invalid connection scope')
     # A public publisher cannot select another provider's identity to revoke it.
     import secrets
     owner=secrets.token_urlsafe(24)
     grant=store.publish(owner,instance,body.get('catalogue'))
     self.send(201,{'path':'/shared/'+grant['capability'],'control':grant['control']});return
    cap,action=self.route()
    if action=='select':
     with store._lock:scope=store._current(cap)['instance']
     store.select(cap,scope,body.get('index'),self.control() or None);self.send(200,{'accepted':True});return
    if action=='heartbeat':store.heartbeat(cap,self.control())
    elif action=='disconnect':store.disconnect(cap,self.control())
    elif action=='lock':store.set_locked(cap,self.control(),body.get('locked'))
    else:raise ShareDenied('Connection unavailable')
    self.send(200,{'updated':True})
   except (ShareDenied,ValueError,TypeError):self.send(403,{'error':'Request unavailable or not permitted'})
   except (BrokenPipeError,ConnectionResetError):pass
 return BoundedHTTPServer(address,Handler)

if __name__=='__main__':
 # Explicit execution only. Nothing is started by importing this module.
 server(('0.0.0.0',int(os.environ.get('PORT','8080')))).serve_forever()