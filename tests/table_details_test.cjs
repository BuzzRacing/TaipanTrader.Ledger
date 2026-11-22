const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Details = require('../web/table-details.js');
const Director = require('../web/table-director.js');
const manifest={ships:2,used:70,capacity:100,guns:6,cannons:1,hull:62,cargo:{tea:50,silk:20,rice:0}};
const passage={sea:2,orders:'run',protect:0,manifest};
const departure={kind:'departure',passage};
assert.deepEqual(Details.passage(departure).manifest.cargo,[['tea',50],['silk',20]]);
assert.equal(Details.passage({kind:'voyage',passage:{sea:99,orders:'invented',protect:-1}}).sea,null);
assert.equal(Details.passage({kind:'voyage',passage:{sea:0,orders:'fight',protect:3}}).sea,0);
assert.equal(Details.passage({kind:'arrival',passage}),null);
assert.equal(Details.passage({kind:'departure'}),null,'old events do not borrow a current manifest');
const receipt={kind:'trade',type:'sell',good:'tea',qty:20,total:400,cash:[1000,1400]};
assert.deepEqual(Details.receipt(receipt),{good:'tea',quantity:20,total:400,buying:false,cashAfter:1400,delta:400});
assert.equal(Details.receipt({...receipt,type:'buy',cash:[1000,600]}).delta,-400);
assert.equal(Details.receipt({...receipt,qty:NaN}),null);
assert.equal(Details.receipt({...receipt,total:-1}),null);
assert.equal(Details.receipt({...receipt,cash:[1000]}).cashAfter,null);
assert.equal(Details.receipt({...receipt,type:'bank'}),null);
assert.equal(Object.hasOwn(Details.receipt(receipt),'profit'),false,'sale proceeds are not invented profit');
const director=new Director(()=>{},()=>1000);
const feed=events=>({game_id:'fixture',focus:{id:'p1',port:'hongkong'},state:{turn:1,phase:'port',news:[]},events});
director.ingest(feed([]));director.ingest(feed([{n:1,type:'sailed',origin:'hongkong',dest:'singapore',passage}]));
assert.equal(director.current.passage,passage);
director.skip();assert.equal(director.current.passage,passage,'voyage keeps the same recorded conditions as departure');
const source=fs.readFileSync(require.resolve('../web/table.js'),'utf8');
const ctx=vm.createContext({TableDetails:Details,scene:{kind:'voyage',passage,from:'hongkong',port:'singapore'},TV:{focus:{}},S:{},T:{},
  D:{weather:['Calm','Fair','Rough','Typhoon'],goods:{tea:{name:'Tea'}}},
  fact:(label,value)=>`${label}: ${value};`,characterOf:()=> 'narrator',portName:x=>x,chooseArt:(_who,mood)=>({mood}),
  Media:{choose:()=>null}});
vm.runInContext(source.slice(source.indexOf('function stageData('),source.indexOf('function camera(')),ctx);
const view=ctx.stageData();assert.equal(view.mood,'storm');assert.match(view.facts,/Rough/);assert.match(view.facts,/Unprotected/);
ctx.scene={kind:'voyage',passage:{sea:0,orders:'fight',protect:4},from:'hongkong',port:'singapore'};
assert.equal(ctx.stageData().mood,'underway');assert.match(ctx.stageData().facts,/4 months/);
console.log('Table context: preserved passage, manifests, weather art, receipt arithmetic and missing-data handling passed');
