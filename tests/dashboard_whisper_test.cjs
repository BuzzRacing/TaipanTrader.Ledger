const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('web/dashboard-whisper.js','utf8');
function harness() {
  const nodes=new Map();
  const node=id=>{
    if(!nodes.has(id)) nodes.set(id,{innerHTML:'',textContent:'',hidden:false,disabled:false,open:false,events:{},classList:{toggle(){}},setAttribute(){},
      addEventListener(k,fn){this.events[k]=fn;},showModal(){this.open=true;},close(){this.open=false;this.events.close?.();}});
    return nodes.get(id);
  };
  let off=true,current=null,onChange=()=>{},now=1000,next=null,fail=false,family=false;
  const spoken=[],requests=[],drops=[],navigations=[];
  const Voice={enabled:()=>true,muted:()=>off,busy:()=>!!current,current:()=>current,
    onChange:fn=>onChange=fn,setMuted:v=>{off=v;},drop:group=>{drops.push(group);if(current?.group===group){current=null;onChange();}},
    say:(items,opts)=>{spoken.push({items,opts});current={...items[0],group:opts.group};onChange();}};
  const ctx={document:{getElementById:node},console:{error(){}},Voice,URLSearchParams,AbortController,setTimeout,clearTimeout,
    Date:{now:()=>now},screenFamily:()=>family,esc:s=>String(s).replaceAll('<','&lt;'),t:k=>k,
    fetch:async url=>{
      requests.push(String(url));if(fail)throw Error('offline');
      if(String(url).includes('/brief?'))return {ok:true,json:async()=>({ok:true,brief:next,clip:{c:'bookmaker',u:'/voice/dirty.mp3',f:'/voice/clean.mp3'}})};
      return {ok:true,arrayBuffer:async()=>new ArrayBuffer(2)};
    }};
  vm.createContext(ctx);vm.runInContext(source+'\nglobalThis.api=DashWhisper;',ctx);
  ctx.api.setup({navigate:x=>navigations.push(x)});
  const click=(id,action)=>node(id).events.click({target:{closest:()=>({dataset:{whisper:action}})}});
  const settle=()=>new Promise(resolve=>setImmediate(resolve));
  return {api:ctx.api,node,spoken,requests,drops,navigations,click,settle,
    input:n=>next=n,unmute:()=>off=false,finish:()=>{current=null;onChange();},time:n=>now=n,failure:()=>fail=true,clean:()=>family=true};
}
const note={id:'a',title:'A verified fact',text:'Full note <safe>',target:{page:'markets',port:'hongkong',good:'tea'}};
(async()=>{
  const h=harness();h.input(note);h.api.sync(note,'bookmaker');
  assert.equal(h.requests.length,0,'Muted devices must not request teaser audio');
  assert(h.node('pw-whisper').innerHTML.includes('A verified fact'));
  assert(!h.node('pw-whisper').innerHTML.includes('whisper-seal'));
  assert(!h.node('pw-whisper').innerHTML.includes('dash.whisper.cue'));
  h.click('pw-whisper','read');
  assert(h.api.isOpen());assert.equal(h.node('whisper-text').textContent,'Full note <safe>');
  assert.equal(h.requests.length,0,'Read must remain silent');
  h.clean();h.click('whisper-listen');await h.settle();
  assert(h.requests[0].includes('persona=bookmaker')&&h.requests[0].includes('part=detail')&&h.requests[0].includes('family=1'));
  assert(h.requests.includes('/voice/clean.mp3'),'Only the clean clip is prefetched on a clean screen');
  assert.equal(h.spoken.length,1);assert.equal(h.node('whisper-listen').textContent,'dash.whisper.stop');
  h.click('whisper-listen');assert(h.drops.includes('dash-whisper'));
  h.click('whisper-show');assert(!h.api.isOpen());assert.equal(h.navigations[0].good,'tea');
  const afterRead=h.requests.length;h.api.sync(note,'bookmaker');await h.settle();assert.equal(h.requests.length,afterRead,'A note already read does not need another teaser');

  const auto=harness();auto.input(note);auto.unmute();auto.api.sync(note,'gamemaster');await auto.settle();
  assert.equal(auto.spoken[0].opts.group,'dash-teaser');
  auto.finish();auto.api.sync(note,'gamemaster');await auto.settle();assert.equal(auto.spoken.length,1);
  const newer={...note,id:'b'};auto.input(newer);auto.api.sync(newer,'gamemaster');await auto.settle();
  assert.equal(auto.spoken.length,1,'New notes respect the teaser cooldown');
  auto.time(92000);auto.api.sync(newer,'gamemaster');await auto.settle();assert.equal(auto.spoken.length,2);
  auto.api.sync(null,'gamemaster');assert(auto.node('pw-whisper').hidden);

  const stale=harness();stale.api.sync(note,'bookmaker');stale.input(newer);stale.click('pw-whisper','hear');await stale.settle();
  assert.equal(stale.spoken.length,0,'A request overtaken by a fresh fact must not play the old fact');
  assert.equal(stale.node('whisper-status').textContent,'dash.whisper.stale');
  stale.failure();stale.click('whisper-listen');await stale.settle();
  assert.equal(stale.node('whisper-status').textContent,'dash.whisper.failed');
  assert.equal(stale.node('whisper-text').textContent,newer.text,'Voice errors preserve readable facts');

  const cancelled=harness();cancelled.input(note);cancelled.api.sync(note,'bookmaker');
  cancelled.click('pw-whisper','hear');cancelled.click('whisper-close');await cancelled.settle();
  assert.equal(cancelled.spoken.length,0,'Closing cancels pending audio');
  console.log('PASS silent reading, cast/family audio, stop/show controls, teaser deduplication and cooldown, stale facts, visible voice failures and pending-audio cancellation');
})().catch(e=>{console.error(e);process.exitCode=1;});
