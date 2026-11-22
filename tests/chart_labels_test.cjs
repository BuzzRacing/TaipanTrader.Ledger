const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const element = attrs => ({
  attrs:{...attrs},
  getAttribute(k) { return this.attrs[k]; },
  setAttribute(k,v) { this.attrs[k]=v; }
});
const ports = [0,82,164,246,328,180].map(y => {
  const rect=element({x:0,y,width:100,height:76});
  const text=element({y:y+20}),leader=element({y2:y+38});
  return {rect,text,leader,querySelector:selector=>selector==='.label-bg'?rect:leader,querySelectorAll:()=>[text]};
});
const chart={querySelectorAll:()=>ports};
const root={querySelectorAll:selector=>selector==='svg.chart.intelligence'?[chart]:[]};
const ctx={document:{addEventListener(){}},console};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('web/chart.js','utf8')+'\nglobalThis.fitChart=Chart.fit;',ctx);
ctx.fitChart(root);
for(let i=0;i<ports.length;i++) {
  const a=ports[i].rect.attrs;
  assert(a.y>=4 && Number(a.y)+Number(a.height)<=596);
  assert.equal(Number(ports[i].leader.attrs.y2),Number(a.y)+Number(a.height)/2);
  for(let j=i+1;j<ports.length;j++) {
    const b=ports[j].rect.attrs;
    assert(Number(a.y)+Number(a.height)+4<=Number(b.y)||Number(b.y)+Number(b.height)+4<=Number(a.y),'Crowded labels overlap');
  }
}
assert(Number(ports[5].rect.attrs.y)>400,'Late label must search beyond two neighbouring positions');
console.log('PASS crowded chart labels remain separated, stay inside chart, and keep leader lines attached');
