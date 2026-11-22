const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const Motion = require('../web/table-motion.js');
const network = Motion.validate(JSON.parse(fs.readFileSync(require.resolve('../web/assets/table/routes.json'),'utf8')));
const ports = JSON.parse(execFileSync('python',['-c','import json,config,engine; engine.configure(config.defaults()); print(json.dumps(engine.static_data()["ports"]))'],{cwd:require('node:path').resolve(__dirname,'..'),encoding:'utf8'}));
const chart=fs.readFileSync(require.resolve('../web/chart.js'),'utf8');
const start=chart.indexOf('const LAND = ')+13,end=chart.indexOf('\n  ];',start)+5;
const land=vm.runInNewContext(chart.slice(start,end).replace(/;\s*$/,''));
const polygons=land.map(poly=>poly.map(([lon,lat])=>({x:(lon-85)*20,y:(35-lat)*600/45})));
function inside(p,polygon){
  let hit=false;
  for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
    const a=polygon[i],b=polygon[j];
    if((a.y>p.y)!==(b.y>p.y) && p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x)hit=!hit;
  }
  return hit;
}
const keys=Object.keys(ports), failures=[];
for(const from of keys)for(const to of keys){
  if(from===to)continue;
  const route=Motion.plan(network,ports,from,to);
  assert.ok(route,`${from} -> ${to} is connected`);
  assert.ok(route.length>0);
  const first=Motion.sample(route,0),last=Motion.sample(route,1);
  assert.ok(Math.hypot(first.x-ports[from].x,first.y-ports[from].y)<1e-6);
  assert.ok(Math.hypot(last.x-ports[to].x,last.y-ports[to].y)<1e-6);
  const reverse=Motion.plan(network,ports,to,from);
  assert.ok(Math.abs(route.length-reverse.length)<1e-6,'reverse voyages take the same course');
  const frame=Motion.frame(route),tx=Math.min(0,Math.max(1000-1000*frame.zoom,500-frame.cx*frame.zoom)),ty=Math.min(0,Math.max(600-600*frame.zoom,300-frame.cy*frame.zoom));
  for(let i=0;i<=Math.ceil(route.length/2);i++){
    const p=Motion.sample(route,i/Math.ceil(route.length/2));
    assert.ok(Object.values(p).every(Number.isFinite));
    assert.ok(p.x*frame.zoom+tx>=-1e-6 && p.x*frame.zoom+tx<=1000+1e-6 && p.y*frame.zoom+ty>=-1e-6 && p.y*frame.zoom+ty<=600+1e-6,'camera includes the entire sea course');
    // Port markers sit inland on this deliberately coarse chart; only their short harbour approaches are exempt.
    const harbour=keys.some(key=>Math.hypot(p.x-ports[key].x,p.y-ports[key].y)<35);
    if(!harbour && polygons.some(poly=>inside(p,poly))){ failures.push(`${from} -> ${to}: land at ${p.x.toFixed(1)},${p.y.toFixed(1)} (${route.keys.join(' / ')})`);break; }
  }
}
assert.deepEqual(failures,[]);
const west=Motion.plan(network,ports,'calcutta','hongkong');
assert.ok(west.keys.includes('malacca_south') && west.keys.includes('singapore'),'Bengal voyages round Malaya');
const gulf=Motion.plan(network,ports,'bangkok','hongkong');
assert.ok(gulf.keys.includes('vietnam_cape'),'Gulf voyages round southern Vietnam');
assert.equal(Motion.plan(network,ports,'missing','hongkong'),null);
assert.throws(()=>Motion.validate({...network,edges:[['missing','bengal']]}),/Invalid sea route edge/);
console.log(`Table sea routes: ${keys.length*(keys.length-1)} directed voyages, coasts, reverse symmetry, endpoints and camera bounds passed`);
