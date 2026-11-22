"use strict";

const TableMotion = {
  validate(network) {
    if (!network?.nodes || !network?.ports || !Array.isArray(network.edges)) throw new Error('Sea routes require nodes, ports and edges');
    const keys = new Set([...Object.keys(network.nodes), ...Object.keys(network.ports)]);
    for (const [name, point] of Object.entries(network.nodes)) {
      if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)) throw new Error('Invalid sea waypoint: ' + name);
    }
    for (const edge of network.edges) {
      if (!Array.isArray(edge) || edge.length !== 2 || edge.some(key => !keys.has(key))) throw new Error('Invalid sea route edge: ' + edge);
    }
    for (const [port, node] of Object.entries(network.ports)) {
      if (!network.nodes[node]) throw new Error('Invalid harbour approach: ' + port);
    }
    return network;
  },
  plan(network, ports, from, to) {
    if (!network || !network.ports[from] || !network.ports[to] || !ports[from] || !ports[to]) return null;
    const points = Object.fromEntries(Object.entries(network.nodes).map(([id, [lon, lat]]) => [id, {x:(lon-85)*20, y:(35-lat)*600/45}]));
    for (const key of Object.keys(network.ports)) if (ports[key]) points[key] = {x:ports[key].x,y:ports[key].y};
    const links = new Map(Object.keys(points).map(key => [key, new Set()]));
    const edges = [...network.edges, ...Object.entries(network.ports)];
    for (const [a,b] of edges) {
      if (links.has(a) && links.has(b)) { links.get(a).add(b); links.get(b).add(a); }
    }
    const distance = new Map([[from,0]]), previous = new Map(), pending = new Set(links.keys());
    while (pending.size) {
      let closest = null;
      for (const key of pending) if (closest === null || (distance.get(key) ?? Infinity) < (distance.get(closest) ?? Infinity)) closest = key;
      if (!Number.isFinite(distance.get(closest))) break;
      pending.delete(closest);
      if (closest === to) break;
      for (const next of links.get(closest)) {
        const a = points[closest], b = points[next];
        const value = distance.get(closest) + Math.hypot(a.x-b.x,a.y-b.y);
        if (value < (distance.get(next) ?? Infinity)) { distance.set(next,value); previous.set(next,closest); }
      }
    }
    if (!distance.has(to)) return null;
    const keys = [to];
    while (keys[0] !== from) keys.unshift(previous.get(keys[0]));
    return {...this.course(keys.map(key=>points[key])), keys};
  },
  course(waypoints) {
    const points = [waypoints[0]];
    for (let i=1;i<waypoints.length-1;i++) {
      const a=waypoints[i-1], b=waypoints[i], c=waypoints[i+1];
      const before=Math.hypot(a.x-b.x,a.y-b.y), after=Math.hypot(c.x-b.x,c.y-b.y);
      const radius=Math.min(10,before*.2,after*.2);
      if (!radius) { points.push(b); continue; }
      const enter={x:b.x+(a.x-b.x)*radius/before,y:b.y+(a.y-b.y)*radius/before};
      const exit={x:b.x+(c.x-b.x)*radius/after,y:b.y+(c.y-b.y)*radius/after};
      points.push(enter);
      for(let step=1;step<=12;step++) {
        const t=step/12,u=1-t;
        points.push({x:u*u*enter.x+2*u*t*b.x+t*t*exit.x,y:u*u*enter.y+2*u*t*b.y+t*t*exit.y});
      }
    }
    points.push(waypoints[waypoints.length-1]);
    let length=0;
    const stops=points.map((p,i)=> { if(i) length+=Math.hypot(p.x-points[i-1].x,p.y-points[i-1].y);return length; });
    return {points,stops,length,path:points.map((p,i)=>`${i?'L':'M'}${p.x} ${p.y}`).join(' ')};
  },
  frame(course) {
    const xs=course.points.map(p=>p.x),ys=course.points.map(p=>p.y);
    const left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys);
    return {cx:(left+right)/2,cy:(top+bottom)/2,zoom:Math.max(1,Math.min(2,1000/(right-left+200),600/(bottom-top+130)))};
  },
  progress(elapsed, duration, reduced = false) {
    if (reduced) return 1;
    const t = Math.max(0, Math.min(1, elapsed / Math.max(1, duration)));
    return t * t * (3 - 2 * t);
  },
  duration(length) {
    return Math.max(6500,Math.min(16000,3000+length*10));
  },
  sample(course, progress) {
    const distance=Math.max(0,Math.min(1,progress))*course.length;
    let index=1;
    while(index<course.stops.length-1 && course.stops[index]<distance) index++;
    const a=course.points[index-1],b=course.points[index];
    const span=course.stops[index]-course.stops[index-1];
    const t=span ? (distance-course.stops[index-1])/span : 0;
    return {
      x:a.x+(b.x-a.x)*t,
      y:a.y+(b.y-a.y)*t,
      angle:Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI+90
    };
  }
};
if (typeof module !== 'undefined') module.exports = TableMotion;
