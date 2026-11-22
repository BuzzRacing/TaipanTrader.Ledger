const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {innerHTML:'',textContent:'',style:{},addEventListener(){},setAttribute(){}});
  return nodes.get(id);
};
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ctx = {document:{getElementById:node,addEventListener(){},querySelector(){}}, window:{addEventListener(){}},
  setInterval(){}, setTimeout(){}, clearTimeout(){}, store(){}, listen(){}, Faces:{}, console, esc,
  money:n=>'$'+n, COLORS:['#e2b24a'], T:{}, Chart:{svg:()=>'<svg viewBox="0 0 1000 600"></svg>'}};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('web/dashboard.js','utf8')+`
  globalThis.testApi = { renderDials, renderDetail, pageMarkets, marketMetrics, marketPortDetail,
    data(d,s,f) { D=d; S=s; F=f; }, detail(k) { detailKind=k; } };
`,ctx);
const api=ctx.testApi;
const d={weather:['Calm','Fair','Squalls','Typhoon'],regions:{a:{name:'North'},b:{name:'South'}},
  ports:{a:{name:'Port A',x:100,y:100},b:{name:'Port B',x:300,y:300}},goods:{tea:{name:'Tea'}}};
const state={years:5,turns_left:48,phase:'port',weather:{a:0,b:3}};
const feed={turn:12,locked:false,houses:[{firm:'House <One>',worth:100,hull:[{hull:.5,crippled:true}]}],
  ports:{a:{prices:{tea:20},base:{tea:25}},b:{prices:{tea:30},base:{tea:25}}},booms:[]};
api.data(d,state,feed);
api.renderDials();
assert.equal(node('dn1').style.transform,'rotate(120.0deg)','One dangerous sea must not be averaged away');
assert.equal(node('dv1').textContent,'3/3');
assert.equal(node('dv2').textContent,'50%');
api.detail('weather');api.renderDetail();
assert(node('detail-body').innerHTML.indexOf('South')<node('detail-body').innerHTML.indexOf('North'));
assert(node('detail-body').innerHTML.includes('optimum="0"'),'Low weather severity is favourable');
api.detail('fleet');api.renderDetail();
assert(node('detail-body').innerHTML.includes('House &lt;One&gt;'));
assert(node('detail-body').innerHTML.includes('50% · Crippled'));
const market=api.pageMarkets();
assert(market.left.includes('$10'),'Price spread is high quote less low quote');
assert(market.left.includes('dealer margins, tax and voyage costs'));
assert(market.right.includes('-20%') && market.right.includes('+20%'));
const metrics=api.marketMetrics([{port:'a',good:'tea',price:20,pct:-.2},{port:'b',good:'tea',price:30,pct:.2}],'tea','change');
assert.equal(metrics.a.value,'-20%');assert.equal(metrics.a.negative,true);
assert.equal(metrics.b.positive,true);
api.data(d,{...state,bans:{b:['tea']}},{...feed,market_effects:[{port:'b',good:'tea',sort:'crash',mult:.4,turns:1}]});
const banned=api.pageMarkets();
assert(banned.left.includes('$0'),'A banned high quote must be excluded from the comparison');
const port=api.marketPortDetail([{port:'b',good:'tea',price:30,pct:.2}],'b','tea');
assert(port.includes('Banned cargo') && port.includes('1 month remaining'));
assert(port.includes('data-market-good="tea"'));
api.data({...d,ports:{a:{name:'Port A',region:'a'},b:{name:'Port B',region:'b'}}},state,feed);
assert.equal(api.marketMetrics([],'tea','weather').b.value,'Typhoon');
assert.equal(api.marketMetrics([],'tea','weather').b.negative,true);
const locked={locked:true,get ports(){throw Error('Private prices were read');}};
api.data(d,state,locked);
const sealed=api.pageMarkets();
assert(sealed.left.includes('Sealed') && !sealed.left.includes('market-cargo'));
api.data(d,{...state,weather:{}},{...feed,houses:[],ports:{}});
api.renderDials();
assert.equal(node('dv2').textContent,'-');
assert(!api.pageMarkets().left.includes('NaN'));
console.log('PASS dangerous-region gauge, fleet conditions, escaped names, quote spreads, monthly changes, map layers, banned-port comparison, live-effect drilldown, locked markets and empty fleet/markets');
