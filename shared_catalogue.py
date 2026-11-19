"""Instance-scoped catalogue leases. Not exposed by HTTP until transport is wired.
Only sanitized catalogue metadata and poster bytes may enter this store.
Jellyfin credentials and source paths remain in the provider connector.
"""
import copy,json,secrets,threading,time

class ShareDenied(Exception): pass

class SharedCatalogues:
    def __init__(self,clock=time.monotonic,lease_seconds=30,max_bytes=64*1024*1024):
        self.clock=clock;self.lease_seconds=lease_seconds;self.max_bytes=max_bytes;self._lock=threading.RLock();self._shares={}

    def _current(self,cap):
        share=self._shares.get(cap)
        if not share or share['until']<=self.clock():
            self._shares.pop(cap,None)
            raise ShareDenied('Catalogue disconnected')
        return share

    @staticmethod
    def _catalogue(payload):
        # Allowlist rather than passing through a server response or account object.
        if not isinstance(payload,dict) or not isinstance(payload.get('items'),list) or len(payload['items'])>2000:
            raise ShareDenied('Invalid catalogue')
        fields={'id','name','type','parent','season','number','library','poster','request','year','overview'}
        rows=[]
        for row in payload['items']:
            if not isinstance(row,dict) or row.get('type') not in ('Movie','Series','Season','Episode'):
                raise ShareDenied('Invalid catalogue entry')
            clean={k:copy.deepcopy(v) for k,v in row.items() if k in fields}
            for key,value in clean.items():
                if value is not None and not isinstance(value,(str,int,float)):
                    raise ShareDenied('Invalid catalogue value')
                if isinstance(value,str) and len(value)>600:raise ShareDenied('Catalogue text too long')
            rows.append(clean)
        columns=payload.get('posterColumns',8);height=payload.get('posterRows',6)
        if type(columns) is not int or type(height) is not int or not 1<=columns<=64 or not 1<=height<=64:raise ShareDenied('Invalid poster layout')
        result={'version':1,'posterColumns':columns,'posterRows':height,'items':rows}
        if len(json.dumps(result,ensure_ascii=False).encode())>1024*1024:raise ShareDenied('Catalogue too large')
        return result

    def publish(self,provider,instance,catalogue,posters=b''):
        if not provider or not instance:raise ShareDenied('Missing connection identity')
        clean=self._catalogue(catalogue)
        if not isinstance(posters,bytes) or len(posters)>8*1024*1024:raise ShareDenied('Invalid posters')
        if posters and not posters.startswith(b'\x89PNG\r\n\x1a\n'):raise ShareDenied('Invalid poster format')
        with self._lock:
            self._shares={k:v for k,v in self._shares.items() if v['until']>self.clock()}
            # Replacing a connection invalidates its previous link immediately.
            self._shares={k:v for k,v in self._shares.items() if not(v['provider']==provider and v['instance']==instance)}
            if len(self._shares)>=64:raise ShareDenied('Too many connections')
            metadata_bytes=len(json.dumps(clean,ensure_ascii=False).encode())
            if sum(v['metadata_bytes']+len(v['posters']) for v in self._shares.values())+metadata_bytes+len(posters)>self.max_bytes:raise ShareDenied('Catalogue capacity reached')
            cap=secrets.token_urlsafe(24);control=secrets.token_urlsafe(32)
            self._shares[cap]={'provider':provider,'instance':instance,'control':control,'catalogue':clean,'metadata_bytes':metadata_bytes,'posters':posters,'until':self.clock()+self.lease_seconds,'selection':None,'locked':False}
            # control stays ONLY in the provider connector; cap is the instance read capability.
            return {'capability':cap,'control':control}

    def set_posters(self,cap,control,posters):
        if not isinstance(posters,bytes) or not posters.startswith(b'\x89PNG\r\n\x1a\n') or len(posters)>8*1024*1024:
            raise ShareDenied('Invalid posters')
        with self._lock:
            share=self._current(cap)
            if not secrets.compare_digest(share['control'],control):raise ShareDenied('Provider approval required')
            self._shares={k:v for k,v in self._shares.items() if v['until']>self.clock()}
            used=sum(v['metadata_bytes']+len(v['posters']) for v in self._shares.values())
            if used-len(share['posters'])+len(posters)>self.max_bytes:raise ShareDenied('Poster capacity reached')
            share['posters']=posters

    def heartbeat(self,cap,control):
        with self._lock:
            share=self._current(cap)
            if not secrets.compare_digest(share['control'],control):raise ShareDenied('Provider approval required')
            share['until']=self.clock()+self.lease_seconds

    def read(self,cap,instance,kind='catalogue'):
        with self._lock:
            share=self._current(cap)
            if share['instance']!=instance:raise ShareDenied('Different instance')
            if kind not in ('catalogue','posters'):raise ShareDenied('Invalid resource')
            return copy.deepcopy(share[kind])

    def select(self,cap,instance,index,control=None):
        with self._lock:
            share=self._current(cap)
            if share['instance']!=instance:raise ShareDenied('Different instance')
            if share['locked'] and (not isinstance(control,str) or not secrets.compare_digest(share['control'],control)):raise ShareDenied('Screen is locked')
            rows=share['catalogue']['items']
            if isinstance(index,bool) or not isinstance(index,int) or index<0 or index>=len(rows) or rows[index]['type'] not in ('Movie','Episode'):
                raise ShareDenied('Choose a movie or episode')
            share['selection']=index

    def set_locked(self,cap,control,locked):
        with self._lock:
            share=self._current(cap)
            if not secrets.compare_digest(share['control'],control):raise ShareDenied('Provider approval required')
            if not isinstance(locked,bool):raise ShareDenied('Invalid lock state')
            share['locked']=locked
    def take_selection(self,cap,control):
        with self._lock:
            share=self._current(cap)
            if not secrets.compare_digest(share['control'],control):raise ShareDenied('Provider approval required')
            result=share['selection'];share['selection']=None;return result

    def disconnect(self,cap,control):
        with self._lock:
            share=self._current(cap)
            if not secrets.compare_digest(share['control'],control):raise ShareDenied('Provider approval required')
            del self._shares[cap]

    def provider_left(self,provider,instance):
        # Called by trusted provider-session teardown, never a viewer-supplied HTTP identity.
        with self._lock:self._shares={k:v for k,v in self._shares.items() if not(v['provider']==provider and v['instance']==instance)}