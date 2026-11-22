const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Motion = require('../web/table-motion.js');

const a = {x:700,y:180}, b = {x:420,y:480};
const course = Motion.course([a,{x:750,y:360},b]);
assert.deepEqual(Object.fromEntries(Object.entries(Motion.sample(course,0)).filter(([k])=>k!=='angle')),a);
assert.deepEqual(Object.fromEntries(Object.entries(Motion.sample(course,1)).filter(([k])=>k!=='angle')),b);
assert.equal(Motion.progress(-100,5000),0);
assert.equal(Motion.progress(6000,5000),1);
assert.equal(Motion.progress(0,5000,true),1,'reduced motion places the ship at landfall immediately');
let previous = -1;
for(let elapsed=0;elapsed<=5000;elapsed+=50){
  const progress = Motion.progress(elapsed,5000);
  assert.ok(progress>=previous && progress<=1,'travel never reverses or overshoots');
  previous=progress;
  const point=Motion.sample(course,progress);
  assert.ok(Object.values(point).every(Number.isFinite));
}
const Director = require('../web/table-director.js');
let now=1000;
const director = new Director(()=>{},()=>now);
director.enqueue('voyage',[{kind:'voyage',duration:6500}]);director.tick();
now+=2000;
const before=Motion.progress(now-director.current.startedAt,5500);
director.pause();now+=30000;director.pause();
assert.equal(Motion.progress(now-director.current.startedAt,5500),before,'resume keeps the exact ship position after a long pause');
now+=500;
assert.ok(Motion.progress(now-director.current.startedAt,5500)>before);

const source=fs.readFileSync(require.resolve('../web/table.js'),'utf8');
const pacing=vm.createContext({director:{},Voice:{muted:()=>false},Date:{now:()=>now}});
vm.runInContext(source.slice(source.indexOf('director.canAdvance ='),source.indexOf('function sceneSound(')),pacing);
const voyage={kind:'voyage',startedAt:now-6000,duration:6500,travelDuration:14000,voiceExpected:true,voiceStarted:true,voiceEndedAt:now-1500};
assert.equal(pacing.director.canAdvance(voyage),false,'a short voice clip cannot cut a long sea route short');
now+=9000;
assert.equal(pacing.director.canAdvance(voyage),true,'landfall can follow completed travel and narration');
assert.equal(Motion.duration(0),6500);assert.equal(Motion.duration(5000),16000);
const choose=source.slice(source.indexOf('function chooseArt('),source.indexOf('function characterOf('));
const dedicated={t:'image',u:'table-host.jpg',g:['table-host'],r:['wallpaper','speaking']};
const wide={t:'image',u:'ledger.jpg',g:['master-shot'],r:['wallpaper','host']};
const portrait={t:'image',u:'portrait.jpg',g:[],r:['portrait'],p:true};
const context=vm.createContext({Media:{items:()=>[wide,dedicated,portrait]},tableArt:{personas:{gamemaster:{host:'bundled.webp'}}}});
vm.runInContext(choose,context);
assert.equal(context.chooseArt('gamemaster','host','one'),dedicated,'explicit Table host art survives its shared wallpaper role');
assert.equal(context.chooseArt('gamemaster','unknown','one'),portrait,'unrelated wide paintings stay out of the figure slot');
context.Media.items=()=>[wide,portrait];
assert.equal(context.chooseArt('gamemaster','host','one').u,'/assets/table/bundled.webp','completed Table art remains available when the gallery lacks its tags');
context.Media.items=(_kind,_who,_role,_video,slot)=>slot==='wallpaper'?[dedicated,wide]:[portrait];
assert.equal(context.chooseArt('gamemaster','host','one'),dedicated,'explicit Table art is requested from the library wallpaper slot');
const mayor={t:'image',u:'mayor.webp',r:['mayor'],p:true},otherMayor={t:'image',u:'other-mayor.webp',r:['mayor']};
context.Media.items=()=>[otherMayor,mayor];
assert.equal(context.chooseArt('mayor','happy','arrival','singapore',{kind:'arrival'}),mayor,'arrival respects the port primary Mayor portrait');
const presentation=vm.createContext({scene:{kind:'arrival',port:'singapore',key:'arrival'},TV:{focus:{}},S:{turn:1},VS:{},T:{},D:{},tableArt:{personas:{}},
  TableDetails:require('../web/table-details.js'),
  characterOf:()=> 'mayor',portName:key=>key,whoOf:()=>({name:'Mayor'}),chooseArt:()=>mayor,
  Media:{choose:(_kind,_subjects,role,options)=>{assert.equal(options.strict,true,'arrival artwork never takes a broad role fallback');return role==='banner'?{u:'singapore-harbour.webp'}:null;}}});
vm.runInContext(source.slice(source.indexOf('function stageData('),source.indexOf('function camera(')),presentation);
assert.equal(presentation.stageData().backdrop.u,'singapore-harbour.webp','an absent arrival painting uses the actual port panorama');
presentation.scene={kind:'voyage',from:'calcutta',port:'hongkong',key:'voyage',mood:'voyage'};
assert.equal(presentation.stageData().mood,'underway','calm voyages request their dedicated new painting');
console.log('Table motion: endpoints, easing, reduced motion, pause continuity and dedicated artwork passed');
