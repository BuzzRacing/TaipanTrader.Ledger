"use strict";

const TableDetails = {
  passage(scene) {
    const source = scene?.passage;
    if (!source || !['departure','voyage'].includes(scene.kind)) return null;
    const nonnegative = value => Number.isFinite(value) && value >= 0;
    const m = source.manifest;
    return {
      sea: Number.isInteger(source.sea) && source.sea >= 0 && source.sea <= 3 ? source.sea : null,
      orders: ['run','fight'].includes(source.orders) ? source.orders : null,
      protect: nonnegative(source.protect) ? Math.floor(source.protect) : null,
      weather: source.weather && typeof source.weather === 'object' && !Array.isArray(source.weather)
        && Object.values(source.weather).every(value => Number.isInteger(value) && value >= 0 && value <= 3) ? {...source.weather} : null,
      manifest: m && ['ships','used','capacity','guns','cannons','hull'].every(key => nonnegative(m[key])) ? {
        ...m, hull: Math.min(100,m.hull),
        cargo: Object.entries(m.cargo || {}).filter(([,qty]) => nonnegative(qty) && qty > 0)
      } : null
    };
  },
  receipt(scene) {
    if (scene?.kind !== 'trade' || !['buy','sell'].includes(scene.type)) return null;
    if (typeof scene.good !== 'string' || !Number.isFinite(scene.qty) || scene.qty <= 0 || !Number.isFinite(scene.total) || scene.total < 0) return null;
    const cash = Array.isArray(scene.cash) && scene.cash.length === 2 && scene.cash.every(Number.isFinite) ? scene.cash : null;
    return { good:scene.good, quantity:scene.qty, total:scene.total, buying:scene.type === 'buy',
      cashAfter:cash ? cash[1] : null, delta:cash ? cash[1]-cash[0] : null };
  }
};
if (typeof module !== 'undefined') module.exports = TableDetails;
