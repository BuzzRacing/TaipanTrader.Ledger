const assert = require('node:assert/strict');
const Director = require('../web/table-director.js');
let now = 100000, shown = [];
const d = new Director(s => shown.push(s), () => now);
const feed = (events=[], extra={}) => ({game_id:'one', events, state:{turn:1,phase:'port',news:[]},focus:{id:'p1',port:'hongkong',jail:{jail:null,plea:null}},...extra});
d.ingest(feed([{n:1,type:'buy',pid:'p1',text:'Old receipt'}]));
assert.equal(d.current, null, 'opening the screen must not replay receipts or show a false jail');
for(let i=0;i<5;i++)d.tick();
assert.equal(shown.length,0,'idle polling must not reset the host voice');
d.ingest(feed([{n:2,type:'buy',pid:'p1',text:'Bought tea.',cash:[1000,500]}]));
assert.equal(d.current.type,'buy'); assert.deepEqual(d.current.cash,[1000,500]);
d.ingest(feed([{n:2,type:'buy',pid:'p1',text:'Bought tea.'}]));
assert.equal(d.queue.length,0,'the same journal event is shown once');
d.ingest(feed([], {focus:{id:'p1',port:'hongkong',storm:{id:1,turn:1,band:'heavy'}}}));
assert.equal(d.current.kind,'storm','a storm interrupts routine trade');
d.pause(); const count=shown.length; now+=50000; d.tick();
assert.equal(shown.length,count,'paused presentation must hold its scene');
d.pause(); d.board(); assert.equal(d.current,null);
d.ingest({...feed([{n:1,type:'sell',text:'Earlier game'}]),game_id:'two'});
assert.equal(d.current,null,'a new game seeds its own monotonic cursor');
now+=1;
d.ingest({...feed([], {focus:{id:'p1',port:'singapore'}}),game_id:'two'});
assert.equal(d.current,null,'a changed port alone must not invent a voyage');

const travel = new Director(s => {}, () => now);
travel.ingest(feed());
const events = [
  {n:1,type:'sailed',pid:'p1',turn:2,origin:'hongkong',dest:'singapore',focus:{id:'p1',port:'hongkong',worth:100},bridge:{text:'Orders sealed.'},narration:{text:'Under sail.'}},
  {n:2,type:'storm_report',pid:'p1',turn:2,report:{id:2,turn:2,lines:{open:'storm.open.heavy.0'}},focus:{id:'p1',worth:90}},
  {n:3,type:'arrived',pid:'p1',turn:2,port:'singapore',welcome:'Welcome ashore.',bridge:{text:'Landfall.'}},
  {n:4,type:'customs_open',pid:'p1',turn:2,report:{port:'singapore',turn:2,status:'declare',welcome:'Your papers.',officer:'officer_singapore'}},
  {n:5,type:'customs_declare',pid:'p1',turn:2,text:'Settled.',report:{port:'singapore',turn:2,status:'verdict',result:{tax:10,lines:[]}},bridge:{text:'Papers settled.'}}
];
travel.ingest(feed(events,{focus:{id:'p1',port:'singapore',worth:80}}));
const sequence=[];
while(travel.current){sequence.push(travel.current);travel.skip();}
assert.deepEqual(sequence.map(s=>s.kind),['departure','voyage','storm','reckoning','landfall','arrival','customs','customs','reckoning','return']);
assert.equal(sequence[0].focus.worth,100,'departure retains its own financial snapshot');
assert.equal(sequence[2].focus.worth,90,'storm retains its own financial snapshot');
travel.ingest(feed(events));
assert.equal(travel.current,null,'polling completed events must not replay them');

const battle = new Director(()=>{},()=>now);
battle.ingest(feed());
battle.ingest(feed([{n:1,type:'battle_result',pid:'p1',report:{id:'fight1',outcome:'won',beat:{frames:[{say:'Fire!',foe:'Come closer.',foe_by:'liyuen',mood:'angry'}]}}}]));
assert.equal(battle.current.who,'bosun'); assert.equal(battle.current.side,'left');
battle.skip(); assert.equal(battle.current.who,'liyuen'); assert.equal(battle.current.side,'right');
battle.skip(); assert.equal(battle.current.kind,'reckoning');
battle.skip(); assert.equal(battle.current,null);
console.log('Table director: cursor, chronology, frozen snapshots, duets, reckoning, pause and reset passed');
