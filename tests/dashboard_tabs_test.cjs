/* The Command Center's tabs (web/dashboard-tabs.js with web/dashboard.js): Watch Mode's timing, the eight tabs,
   the context bar, the five new pages, sealed pages with rivals at the table, and escaping.
   Run from the project folder:  node tests/dashboard_tabs_test.cjs */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {innerHTML:'',textContent:'',style:{setProperty(){}},dataset:{},classList:{toggle(){},add(){},remove(){}},
    addEventListener(){},setAttribute(){},querySelector(){return null;}});
  return nodes.get(id);
};
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const saved = {};
const ctx = {document:{getElementById:node,addEventListener(){},querySelector(){return null;},hidden:false}, window:{addEventListener(){},innerWidth:1366,innerHeight:1024},
  setInterval(){}, setTimeout(){}, clearTimeout(){}, listen(){}, Faces:{}, console, esc, Element:function(){},
  store(k,v){ if (v === undefined) return saved[k] ?? null; if (v === null) delete saved[k]; else saved[k] = v; return null; },
  money:n=>(n<0?'-':'')+'$'+Math.abs(n), COLORS:['#e2b24a','#79c6a5'], T:{}, brandName:()=>'Test',
  Chart:{svg:o=>`<svg viewBox="0 0 1000 600" data-weather="${Object.values(o.weather||{}).join('')}"></svg>`}};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('web/dashboard-tabs.js','utf8')+'\n'+fs.readFileSync('web/dashboard.js','utf8')+`
  globalThis.api = { DashTabs, PAGES, BUILDERS, available, tabTitle, TURN_MS, IDLE_MS, renderHead:()=>{ if (TABS) update("pw-context", TABS.contextHtml()); },
    data(d,s,f) { D=d; S=s; F=f; previous.clear(); }, page:()=>page, setPage(k){ page=k; } };
`,ctx);
const { api } = ctx, DT = api.DashTabs;

// ---- the eight tabs, in the approved order, each with a page behind it
assert.equal(JSON.stringify(api.PAGES.map(p=>p.k)), JSON.stringify(['now','lanes','markets','weather','fleet','treasury','race','wire']));
assert.equal(JSON.stringify(api.PAGES.map(p=>api.tabTitle(p.k))), JSON.stringify(['Now','Atlas','Trade','Weather','Fleet','Treasury','Career','Wire']));
for (const p of api.PAGES) assert.equal(typeof api.BUILDERS[p.k], 'function', p.k+' has a page');
assert.equal(api.page(), 'now', 'the Dashboard opens on Now');
assert.equal(api.TURN_MS, 12000); assert.equal(api.IDLE_MS, 60000);

// ---- Watch Mode: 12 seconds a tab; a touch holds it for a minute; a pin, a dialog or a hidden window holds it
const base = { on:true, held:false, busy:false, hidden:false, pageAt:100000, lastTouch:0 };
assert.equal(DT.dueAt(base), 112000);
assert.equal(DT.dueAt({...base, lastTouch:105000}), 165000, 'a touch pushes the turn out to a minute after it');
assert.equal(DT.dueAt({...base, lastTouch:1000}), 112000, 'an old touch no longer holds the page');
for (const k of ['held','busy','hidden']) assert.equal(DT.dueAt({...base, [k]:true}), null, k+' holds the page');
assert.equal(DT.dueAt({...base, on:false}), null);
assert.equal(DT.progress(base, 106000).frac, 0.5);
assert.equal(DT.progress(base, 106000).note, 'touring the tabs');
const waiting = DT.progress({...base, lastTouch:105000}, 110000);
assert.equal(waiting.frac, 0); assert.equal(waiting.note, 'resumes in 43s');
assert.equal(DT.progress({...base, held:true}, 106000).frac, 1);
assert.equal(DT.progress({...base, on:false}, 106000).note, 'off');
// the drawer's ticks: unticked tabs are left out of the tour, kept on this device, and never all of them
assert.equal(JSON.stringify(DT.tour(new Set(['wire','fleet']))), JSON.stringify(['now','lanes','markets','weather','treasury','race']));
assert.equal(DT.tour(new Set(DT.KEYS)).length, 8, 'unticking everything still tours');
DT.writeSkip(new Set(['wire'])); assert.equal(JSON.stringify([...DT.readSkip()]), JSON.stringify(['wire']));
saved.seatrader_dash_watch_skip = 'wire,bogus'; assert.equal(JSON.stringify([...DT.readSkip()]), JSON.stringify(['wire']));
DT.writeSkip(new Set()); assert.equal(saved.seatrader_dash_watch_skip, undefined);

// ---- an open solo game
const d = {weather:['Calm','Fair','Squalls','Typhoon'],regions:{a:{name:'North <Sea>'},b:{name:'South Sea'}},
  ports:{a:{name:'Port A',x:100,y:100,region:'a'},b:{name:'Port B',x:300,y:300,region:'b'}},goods:{tea:{name:'Tea'}},
  voyage_risk:{risk_min:.6,risk_max:1.8,storm_chance:[0,.02,.1,.3]},brand:{}};
const months = [{turn:0,date:'Jan 1860',worth:1000},{turn:1,date:'Feb 1860',worth:4000},{turn:2,date:'Mar 1860',worth:2500}];
const solo = {turn:2,locked:false,date:'Mar 1860',
  houses:[{id:'p1',firm:'House <One>',name:'Ann',color:0,port:'a',worth:2500,months,hull:[{hull:.5,crippled:true},{hull:.9,crippled:false}],legs:[],lanes:[]}],
  context:{date:'Mar 1860',turn:2,phase:'port',months_total:60,months_left:58,seas:{a:1,b:3},worst_sea:{region:'b',level:3},forecast_accuracy:.8,houses:1,
    captain:{id:'p1',firm:'House <One>',port:'a',dest:null,at_sea:false,worth:2500,worth_change:-1500,rank:'Trader',fleet:{ships:2,crippled:1,hull:.7}}},
  market_effects:[{port:'a',good:'tea',sort:'boom',mult:2,turns:1}],booms:[],deals:[],lane_profit:{},ports:{},
  tape:[{n:1,turn:1,type:'sailed',pid:'p1',origin:'a',dest:'b'},{n:2,turn:2,type:'storm_damage',pid:'p1'},{n:3,turn:2,type:'arrived',pid:'p1',port:'b'}]};
const state = {years:5,turns_left:58,phase:'port',date:'Mar 1860',weather:{a:1,b:3},crackdown:['b'],sea:[]};
api.data(d,state,solo);

const bar = DT.contextHtml();
for (const want of ['Port A','$2500','-$1500','70%','1 crippled','Typhoon','South Sea','Trader']) assert(bar.includes(want), 'context bar shows '+want);
assert(bar.includes('data-page="treasury"') && bar.includes('data-page="weather"') && bar.includes('data-page="fleet"'), 'each chip opens its tab');
assert(/class="cx-chip warn"/.test(bar), 'a crippled ship marks the fleet chip');
solo.context.captain.at_sea = true; solo.context.captain.dest = 'b';
assert(DT.contextHtml().includes('Bound for') && DT.contextHtml().includes('Port B'));
solo.context.captain.at_sea = false; solo.context.captain.dest = null;

const now = api.BUILDERS.now();
assert(now.left.includes('58') && now.left.includes('of 60'));
assert(now.left.includes('$2500') && now.left.includes('-$1500'));
assert(now.left.includes('1 boom or crash running'));
assert(now.left.includes('Port B'), 'the banned port is named');
assert(now.right.indexOf('dropped anchor') < now.right.indexOf('sailed'), 'the wire is newest first');

const wx = api.BUILDERS.weather();
assert(wx.left.includes('data-weather="13"'), 'the chart is given this snapshot\'s forecast');
assert(wx.right.indexOf('South Sea') < wx.right.indexOf('North &lt;Sea&gt;'), 'worst sea first, names escaped');
assert(wx.right.includes('80%'), 'how often a forecast holds');
assert(wx.right.includes('30%') && wx.right.includes('×0.6') && wx.right.includes('×1.8'), 'storm chances are the server\'s own');
assert(!/safe|guarantee/i.test(wx.left + wx.right), 'no route is called safe');

const fleet = api.BUILDERS.fleet();
assert(fleet.left.includes('50%') && fleet.left.includes('Crippled') && fleet.left.includes('90%') && fleet.left.includes('Sound'));
assert(fleet.right.includes('Storm damage') && !fleet.right.includes('dropped anchor'), 'only storms and fights');

const tr = api.BUILDERS.treasury();
assert(tr.left.indexOf('Mar 1860') < tr.left.indexOf('Feb 1860'), 'newest month first');
assert(tr.left.includes('+$3000') && tr.left.includes('-$1500'));
assert(tr.right.includes('Best month') && tr.right.includes('+$3000') && tr.right.includes('Worst month') && tr.right.includes('-$1500'));
assert(!tr.right.includes('pw-stamp'), 'nothing is sealed in an open solo game');

const wire = api.BUILDERS.wire();
assert.equal((wire.left.match(/<li /g)||[]).length, 3);
assert.equal((wire.right.match(/<li /g)||[]).length, 2, 'this month only on the right');
assert(wire.left.includes('House &lt;One&gt;') && !wire.left.includes('House <One>'), 'firm names are escaped');

// ---- rivals at the table: every tab stays, private pages are sealed, no Captain's chips
const rivals = {...solo, locked:true, market_effects:undefined, deals:undefined, lane_profit:undefined, ports:undefined, booms:undefined,
  houses:[solo.houses[0], {id:'p2',firm:'Two & Co.',name:'Bo',color:1,port:'b',worth:9000,months:[{turn:0,date:'Jan 1860',worth:1000},{turn:2,date:'Mar 1860',worth:9000}],hull:[],legs:[],lanes:[]}],
  context:{...solo.context, houses:2, captain:null}};
api.data(d,state,rivals);
assert.equal(api.available().length, 8, 'no tab is hidden with rivals at the table');
const tabs = DT.tabsHtml('now', true);
assert.equal((tabs.match(/role="tab"/g)||[]).length, 8);
assert.equal((tabs.match(/ sealed"/g)||[]).length, 2, 'Trade and Treasury are marked sealed');
assert(api.BUILDERS.markets().left.includes('pw-stamp'), 'Trade shows the stamp');
const sealedTr = api.BUILDERS.treasury();
assert(sealedTr.right.includes('pw-stamp') && sealedTr.left.includes('Two &amp; Co.'), 'Treasury keeps public worth and seals the books');
const pub = DT.contextHtml();
assert(pub.includes('Two &amp; Co.') && pub.includes('Houses') && !pub.includes('Net worth') && !pub.includes('Rank'), 'table-wide chips only');
assert(!api.BUILDERS.now().left.includes('boom or crash'), 'no market facts without the market block');

// ---- the lobby: nothing sailed, nothing invented
api.data(d,{...state,phase:'lobby',crackdown:[]},{...solo,houses:[],tape:[],context:{...solo.context,phase:'lobby',houses:0,captain:null,months_left:60}});
const lobby = api.BUILDERS.now();
assert(lobby.left.includes('Waiting for captains') && lobby.right.includes('Nothing on the wire yet.'));
assert(!DT.contextHtml().includes('Typhoon'), 'no forecast chip before a game starts');
for (const k of ['weather','fleet','treasury','wire']) assert(api.BUILDERS[k]().left.length > 0, k+' draws with nothing to show');

// ---- the Monsoon Observatory: the Weather tab's three pages
api.data(d,state,{...solo,
  weather:{seas:{a:{level:1,harbours:['a']},b:{level:3,harbours:['b']}},forecast_accuracy:.8,storm_chance:[0,.02,.1,.3],
    history:{storms:[{turn:1,date:'Feb 1860',pid:'p1',band:'savage',typhoon:true,ships:2,damage:40,worst:55,offcourse:'b',cargo:12,guns:3}],
      totals:{voyages:5,storms:1,typhoons:1,offcourse:1,wrecks:0},seas:{a:{months:2,held:2},b:{months:2,held:1}}}},
  routes:{from:'a',at_sea:false,dest:null,routes:[{dest:'b',distance:579,risk:1.65,level:3,storm:.42,pirates:.062,lord:.021,banned:['tea']}],
    inputs:{forecast_accuracy:.8,storm_risk_cap:1.4,risk_min:.6,risk_max:1.8,allure:1.54,flag_deter:1,lord_pull:1.92,protect:0,protect_save:.85,offcourse:.15,hull:.7,cargo_cost:6955}}});
assert.equal(JSON.stringify(DT.SUBS.weather), JSON.stringify(['now','routes','history']));
DT.setSub('weather','now'); assert.equal(DT.subOf('weather'), 'now'); assert.equal(DT.subOf('fleet'), '');
const obsNow = api.BUILDERS.weather();
assert.equal((obsNow.left.match(/data-sub=/g)||[]).length, 3, 'three pages to choose from');
assert(/class="cc-sub on" aria-pressed="true" data-sub="now"/.test(obsNow.left));
assert(obsNow.right.includes('your fleet') && obsNow.right.includes('Port B'), 'the fleet\'s sea is marked, harbours are listed');
DT.setSub('weather','bogus'); assert.equal(DT.subOf('weather'), 'now', 'an unknown page is ignored');
DT.setSub('weather','routes');
const rts = api.BUILDERS.weather();
assert(rts.left.includes('From Port A') && rts.left.includes('class="wxl3"') && rts.left.includes('>42%<'), 'the route is drawn with its forecast and storm chance');
assert(rts.right.includes('data-route="b"') && rts.right.includes('42%') && rts.right.includes('6.2%') && rts.right.includes('2.1%'));
assert(rts.right.includes('Typhoon') && rts.right.includes('&times;1.65') && rts.right.includes('ban'));
assert(rts.right.includes('70%') && rts.right.includes('$6955') && rts.right.includes('None'), 'what is at stake');
assert(!/\bsafe\b|guarantee|recommend|divert/i.test(rts.left + rts.right), 'odds, never advice');
const why = DT.detail('route:b');
assert.equal(why.title, 'Port A → Port B');
for (const want of ['&times;1.65','Distance 579','30% at Typhoon × 1.40','×1.4','×1.54','×1.92','Tea','holds about 80%']) assert(why.body.includes(want), 'the explanation shows '+want);
assert.equal(DT.detail('route:nowhere'), null); assert.equal(DT.detail('weather'), null);
solo.routes = undefined;
const protectedFleet = {...solo, routes:{from:'a',at_sea:true,dest:'b',routes:[{dest:'b',distance:100,risk:.6,level:1,storm:.012,pirates:.03,lord:0,banned:[]}],inputs:{protect:3,storm_risk_cap:1.4,hull:1,cargo_cost:0,forecast_accuracy:.8}},weather:{seas:{a:{level:1,harbours:['a']},b:{level:1,harbours:['b']}},storm_chance:[0,.02,.1,.3],forecast_accuracy:.8}};
api.data(d,state,protectedFleet);
const prot = api.BUILDERS.weather();
assert(prot.left.includes('Under sail for Port B') && prot.right.includes('3 months left') && prot.right.includes('1.2%'));
assert(DT.detail('route:b').body.includes('She leaves a protected fleet alone'));
DT.setSub('weather','history');
api.data(d,state,{...solo,weather:{seas:{a:{level:1,harbours:['a']},b:{level:3,harbours:['b']}},storm_chance:[0,.02,.1,.3],
  history:{storms:[{turn:1,date:'Feb 1860',pid:'p1',band:'savage',typhoon:true,ships:2,damage:40,worst:55,offcourse:'b',cargo:12,guns:3}],totals:{voyages:5,storms:1,typhoons:1,offcourse:1,wrecks:0},seas:{a:{months:2,held:2},b:{months:2,held:1}}}}});
const hx = api.BUILDERS.weather();
for (const want of ['Feb 1860','Typhoon','savage','2 ships hit, 40 hull points lost','blown to Port B','12 units overboard','3 guns lost']) assert(hx.left.includes(want), 'history shows '+want);
assert(hx.right.includes('1 of 2 months') && hx.right.includes('50%') && hx.right.includes('100%'), 'how often each forecast came true');
// Watch Mode coming round again shows the next page; with rivals the routes are sealed and the losses are not sent
DT.setSub('weather','now'); DT.lap('weather'); assert.equal(DT.subOf('weather'), 'routes');
DT.lap('weather'); DT.lap('weather'); assert.equal(DT.subOf('weather'), 'now'); DT.lap('fleet');
DT.setSub('weather','routes'); api.data(d,state,{...rivals,weather:{seas:{a:{level:1,harbours:['a']},b:{level:3,harbours:['b']}},storm_chance:[0,.02,.1,.3],history:{storms:[{turn:1,date:'Feb 1860',pid:'p2',band:'rough',typhoon:false,ships:1,damage:9,worst:80,offcourse:null}],totals:{voyages:2,storms:1,typhoons:0,offcourse:0,wrecks:0},seas:{}}}});
const sealedRt = api.BUILDERS.weather();
assert(sealedRt.left.includes('pw-stamp') && !sealedRt.right.includes('data-route'), 'routes are sealed with rivals at the table');
DT.setSub('weather','history');
const pubHx = api.BUILDERS.weather().left;
assert(pubHx.includes('Two &amp; Co.') && pubHx.includes('1 ship hit, 9 hull points lost') && !pubHx.includes('overboard'), 'a rival\'s storm is news; its losses are not shown');
DT.setSub('weather','now');

// ---- the Captain's Atlas: six layers on the chart, a ranked list, a port's dossier
const portRow = (over) => ({here:false,home:false,services:{bank:true,lender:false,warehouse:true,shipyard:false},rep:50,band:2,
  effects:{audit:1,margin:0,yard:0,match:0,tax_cut:0,avoid:0},tax:{base:.03,mine:.03,home_free:false,share_cut:0},
  shares:{mine:0,total:10,left:10,patron:null,patron_me:false},warehouse:null,commissions:[],crackdown:false,banned:[],...over});
const atlasFeed = {...solo, context:{...solo.context},
  atlas:{standing_on:true,tax_holiday:0,shares:{earned:4,placed:3,free:1,cap:10,value:900000},ports:{
    a:portRow({here:true,home:true,rep:96,band:4,effects:{audit:1,margin:0,yard:0,match:0,tax_cut:.5,avoid:0},tax:{base:.03,mine:0,home_free:true,share_cut:0},
      warehouse:{goods:{tea:1200},cap:10000,used:1200,rent:0,empty:false,home:true}}),
    b:portRow({rep:12,band:0,effects:{audit:2,margin:.05,yard:.2,match:0,tax_cut:0,avoid:0},tax:{base:.04,mine:.028,home_free:false,share_cut:.3},
      shares:{mine:3,total:10,left:5,patron:'House <One>',patron_me:true},commissions:[7],crackdown:true,banned:['tea']})}},
  career:{commissions:{active:[{id:7,port:'b',text:'Sell 500 Tea in Port B',due_date:'Dec 1860'}],offers:{short:{id:9,port:'a',text:'Supply run to Port A'}}}}};
api.data(d,state,atlasFeed);
assert.equal(JSON.stringify(DT.SUBS.lanes), JSON.stringify(['standing','tax','shares','stores','jobs','bans']));
DT.setSub('lanes','standing'); DT.setPort('');
let at = api.BUILDERS.lanes();
assert.equal((at.left.match(/data-sub=/g)||[]).length, 6, 'six layers');
assert.equal((at.left.match(/<g class="cc-pin /g)||[]).length, 2, 'a pin for every port');
assert(at.left.includes('cc-pin b4') && at.left.includes('cc-pin b0') && at.left.includes('>96<') && at.left.includes('>12<'));
assert(at.right.indexOf('Port A') < at.right.indexOf('Port B') && at.right.includes('Favoured') && at.right.includes('Hostile'), 'standing, best first, band named');
assert(!at.left.includes('pw-threads'), 'the sea-lane threads are gone');
DT.setSub('lanes','tax'); at = api.BUILDERS.lanes();
assert(at.right.includes('No tax in your home port.') && at.right.includes('2.8%') && at.right.includes('Down from 4%'));
DT.setSub('lanes','shares'); at = api.BUILDERS.lanes();
assert(at.left.includes('>3/10<') && at.left.includes('cc-pin crown') && at.left.includes('3 of your 4 shares are placed and 1 are free'));
assert(at.right.includes('Patron: House &lt;One&gt;') && at.right.includes('5 unsold'));
DT.setSub('lanes','stores'); at = api.BUILDERS.lanes();
assert(at.right.includes('Home warehouse, no rent') && at.right.includes('1k/10k') && !at.right.includes('data-port="b"'), 'only ports with a warehouse');
DT.setSub('lanes','jobs'); at = api.BUILDERS.lanes();
assert(at.right.includes('Sell 500 Tea in Port B') && at.right.includes('On offer: Supply run to Port A'));
DT.setSub('lanes','bans'); at = api.BUILDERS.lanes();
assert(at.right.includes('data-port="b"') && at.right.includes('Tea') && !at.right.includes('data-port="a"'));
// a port tapped: its dossier fills the right leaf, with the way back
DT.setPort('b'); assert.equal(DT.port(), 'b'); at = api.BUILDERS.lanes();
assert(at.left.includes('class="ring"') && /cc-pin[^"]* on" data-port="b"/.test(at.left), 'the tapped port is ringed');
for (const want of ['Port B','South Sea','All ports','12 &middot; Hostile','desk checks ×2','dealers take 5% more','the yard charges 20% more','2.8%','Down from 4%','Your shares take 30% off','3 of 10','Patron: House &lt;One&gt;','Sell 500 Tea in Port B','due Dec 1860','Banned here','Bank','Warehouse'])
  assert(at.right.includes(want), 'the dossier shows '+want);
assert(!at.right.includes('Moneylender') && !at.right.includes('Shipyard'), 'only the services the port has');
DT.setPort('a'); at = api.BUILDERS.lanes();
for (const want of ['Fleet here','Home port','96 &middot; Favoured','tax cut 50%','No tax in your home port.','1,200 of 10,000','Tea 1,200','On offer']) assert(at.right.includes(want), 'home dossier shows '+want);
DT.setPort('nowhere'); assert.equal(DT.port(), '', 'an unknown port goes back to the list');
// Watch Mode: the next layer, over the port the fleet lies in
DT.setSub('lanes','standing'); DT.lap('lanes'); assert.equal(DT.subOf('lanes'), 'tax'); assert.equal(DT.port(), 'a');
// rivals: shares and bans are public knowledge and still draw; the rest is sealed; no dossier figures
DT.setPort(''); DT.setSub('lanes','standing');
api.data(d,{...state,bans:{b:['tea']}},{...rivals,ports:{a:{shares:{p1:2,p2:1},total:10},b:{shares:{},total:10}}});
at = api.BUILDERS.lanes();
assert(at.right.includes('pw-stamp') && !at.left.includes('<rect'), 'standing is sealed and no figure is drawn');
DT.setSub('lanes','shares'); at = api.BUILDERS.lanes();
assert(at.left.includes('>3/10<') && at.right.includes('3 of 10 held'), 'who holds a port\'s shares is public');
DT.setSub('lanes','bans'); at = api.BUILDERS.lanes();
assert(at.right.includes('Tea') && at.right.includes('data-port="b"'));
DT.setPort('b'); at = api.BUILDERS.lanes();
assert(at.right.includes('pw-stamp') && at.right.includes('Banned here') && !at.right.includes('Standing'), 'a public dossier holds only public facts');
DT.setPort(''); DT.setSub('lanes','standing');

// ---- the full-width stage: the tower stands on Career, the chalkboard on Now, the dials are retired
api.data(d,state,solo);
const career = api.BUILDERS.race();
assert(career.right.includes('cc-tower') && career.right.includes('tw-row') && career.right.includes('House &lt;One&gt;') && career.right.includes('Standings'), 'the timing tower is on Career');
const nowPage = api.BUILDERS.now();
assert(nowPage.right.includes('cc-chalk') && nowPage.right.includes('Mar 1860') && nowPage.right.includes('-$1500'), 'the month times are on Now');
vm.runInContext('renderTower(); renderChalk(); renderDials();', ctx);
assert.equal(node('pw-tower').innerHTML, '', 'the side tower is not drawn');
assert.equal(node('pw-chalk').innerHTML, '', 'the side chalkboard is not drawn');
assert.equal(node('pw-dials').innerHTML, '', 'the dials are not drawn');

// ---- the drawer
const drawer = DT.drawerHtml('weather', new Set(['wire']));
assert.equal((drawer.match(/data-watch=/g)||[]).length, 8);
assert.equal((drawer.match(/ checked/g)||[]).length, 7);
assert(/drawer-go on" data-page="weather"/.test(drawer));
console.log('PASS eight tabs, Watch Mode timing and tour, context bar, five new pages, the Observatory (now, routes, explanations, history), the Atlas (six layers, lists, dossiers), the full-width stage, sealed pages with rivals, empty lobby, escaping and the drawer');
