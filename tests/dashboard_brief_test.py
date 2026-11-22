"""Dashboard observations are factual, visibility-limited, family-safe, and server-planned."""
import copy
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import dashboard_brief
import engine
import strings
import voice

cfg=config.defaults()
engine.configure(cfg,strings.resolve(cfg))
ports=list(engine.PORTS)[:2]
good=next(iter(engine.GOODS))
region=next(iter(engine.REGIONS))
feed={'game_id':'test','turn':2,'locked':False,'houses':[{'firm':'Jade Dragon','hull':[{'hull':.8,'crippled':False}]}],
      'market_effects':[],'ports':{ports[0]:{'prices':{good:20}},ports[1]:{'prices':{good:40}}}}
state={'phase':'port','weather':{region:0},'bans':{}}
brief=dashboard_brief.build(feed,state)
assert brief['kind']=='spread' and '20' in brief['text'] and '40' in brief['text']
assert 'tax' in brief['text'] and 'prices may change' in brief['text']
assert not re.search(r'\d',brief['speech'])
assert dashboard_brief.build(feed,dict(state,phase='lobby')) is None
assert dashboard_brief.build(feed,dict(state,phase='ended')) is None
assert dashboard_brief.build(dict(feed,ports={}),state) is None
ban=dict(state,bans={ports[1]:[good]})
assert dashboard_brief.build(feed,ban) is None, 'Illegal high quote must not be an opportunity'
effect={'port':ports[0],'good':good,'sort':'boom','turns':1,'mult':2.4}
boom=dict(feed,market_effects=[effect])
expiring=dashboard_brief.build(boom,state)
assert expiring['kind']=='expiring' and 'one month' in expiring['text']
assert not re.search(r'\d',expiring['speech'])
assert dashboard_brief.build(boom,dict(state,bans={ports[0]:[good]}))['kind']=='ban'
assert dashboard_brief.build(dict(feed,market_effects=[dict(effect,turns=0)],ports={}),state) is None
weather=dashboard_brief.build(boom,dict(state,weather={region:3}))
assert weather['kind']=='weather' and 'current weather' in weather['text']
assert dashboard_brief.build(boom,dict(state,weather={region:2}))['kind']=='expiring'
assert weather['id'] != dashboard_brief.build(boom,dict(state,weather={region:2}))['id']
class Public(dict):
    def get(self,key,default=None):
        if key in ('ports','market_effects'): raise AssertionError('Private market block read')
        return super().get(key,default)
public=Public(feed,locked=True)
assert dashboard_brief.build(public,state) is None
assert dashboard_brief.build(public,dict(state,weather={region:3}))['kind']=='weather'
fleet=copy.deepcopy(public)
fleet['houses'][0]['hull'][0]['crippled']=True
assert dashboard_brief.build(fleet,state)['kind']=='fleet'
clean_goods={good:dict(engine.GOODS[good],name='Clean Cargo')}
clean_text=dict(engine.TEXT,**strings.FAMILY)
clean=dashboard_brief.build(boom,state,clean_text,clean_goods)
assert 'Clean Cargo' in clean['text'] and 'Clean Cargo' in clean['speech']
class Planner:
    calls=[]
    def ready(self): return True
    def _clip(self,text,cid): self.calls.append((text,cid));return {'c':cid,'u':'/voice/test.mp3'}
planner=Planner()
reply=dashboard_brief.voice_reply(expiring,'bookmaker','detail',planner,engine.TEXT)
assert reply['clip']['c']=='bookmaker' and planner.calls[-1][0]==expiring['speech']
reply=dashboard_brief.voice_reply(expiring,'bookmaker','teaser',planner,engine.TEXT)
assert planner.calls[-1][0]==engine.TEXT['dash.whisper.teaser.bookmaker']
for cid,part in [('outsider','detail'),('bookmaker','arbitrary')]:
    try: dashboard_brief.voice_reply(expiring,cid,part,planner,engine.TEXT)
    except ValueError: pass
    else: raise AssertionError('Invalid voice request was accepted')
planner.ready=lambda:False
assert dashboard_brief.voice_reply(expiring,'bookmaker','detail',planner,engine.TEXT)['clip'] is None
assert dashboard_brief.voice_reply(None,'bookmaker','detail',planner,engine.TEXT)['brief'] is None
# Exercise the real clip registry without synthesizing or reading a key.
plan=voice.Planner()
vcfg=copy.deepcopy(cfg);vcfg['characters']['bookmaker']['voice_id']='dashboard-test-voice'
plan.configure(vcfg,strings.resolve(vcfg));plan.ready=lambda:True
registered=dashboard_brief.voice_reply(expiring,'bookmaker','detail',plan,engine.TEXT)
assert registered['clip']['u'].startswith('/voice/')
print('PASS truthful insights, priority, no filler, bans, expired effects, public visibility, family names, number-free speech and bounded server-planned clips')

# Exercise the actual GET routes without sockets, files, secrets, or synthesis.
import threading
import types
import server
server.HUB=types.SimpleNamespace(cond=threading.RLock(),version=7,present=lambda:[],
    game=types.SimpleNamespace(s={'phase':'port','weather':{},'crackdown':{}},banned=lambda k:[]))
server.dashboard_feed.view=lambda game,present: copy.deepcopy(boom)
server.voice.PLAN=planner
request=object.__new__(server.Handler)
request._send=lambda code,body,*args: (code,body)
request.path='/api/dashboard'
code,body=request._get()
assert code==200 and body['brief']['kind']=='expiring'
request.path='/api/dashboard/brief?persona=bookmaker&part=detail'
code,body=request._get()
assert code==200 and body['brief']['id']==expiring['id'] and body['clip'] is None
request.path='/api/dashboard/brief?persona=outsider&part=detail'
assert request._get()[0]==400
server.dashboard_feed.view=lambda game,present: copy.deepcopy(dict(feed,locked=True))
request.path='/api/dashboard/brief?persona=bookmaker&part=detail'
code,body=request._get()
assert code==200 and body['brief'] is None and body['clip'] is None
request.path='/api/dashboard?family=1'
code,body=request._get()
assert code==200 and body['brief'] is None
print('PASS dashboard HTTP feed/voice contracts, invalid-speaker rejection, disabled audio and multiplayer disclosure gates')
