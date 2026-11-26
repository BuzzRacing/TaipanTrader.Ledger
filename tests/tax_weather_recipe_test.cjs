"use strict";
// The tax-desk and weather recipes in Admin > Media Library > Recipes: each recipe role is one exact picture
// (role + tags), counted that way for the family-friendly library.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const context = {
  window: {}, console,
  document: { addEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, body: { classList: { add() {}, remove() {} } } },
  localStorage: { getItem() { return null; }, setItem() {} },
  esc(value) { return String(value); },
  CFG: { ranks: [], characters: {}, ships: {}, goods: {} },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/media-admin.js", "utf8"), context);
const media = context.window.SeaTraderMedia;
const M = media._state;
const eq = (a, b, m) => assert.equal(JSON.stringify(a), JSON.stringify(b), m);   // arrays made inside the vm are from another realm

const TAX = {
  tax_entry_sly: { role: "sly", need: ["sly"], tags: ["sly"], clean: "Sly prompt", aspect: "3:4" },
  tax_entry_hungry: { role: "idle", need: ["hungry"], tags: ["hungry"], clean: "Hungry prompt", aspect: "3:4" },
};
const WET = {
  weather_clean_calm: { role: "weather", need: ["weather-calm"], tags: ["weather", "weather-calm"],
    clean: "Calm prompt", variants: ["Calm prompt", "Another angle"], aspect: "3:4" },
};
const pic = (subject, role, tags, nsfw = false) => ({
  type: "image", kind: "persona", subject, roles: [role], tags, nsfw, enabled: true, missing: false,
});
M.lib = {
  kinds: { persona: { label: "Personas", one: "Persona", roles: [] } },
  subjects: { persona: [["officer_a", "A"], ["officer_b", "B"], ["crier", "Tommy"]] },
  scene_prompts: { officer_a: TAX, crier: WET },
  virtual_roles: { tax_entry_sly: "Sly", tax_entry_hungry: "Hungry", weather_clean_calm: "Calm" },
  items: [
    pic("officer_a", "sly", ["sly"]),
    pic("officer_a", "idle", ["bored"]),
    pic("crier", "weather", ["weather-calm"], true),
    pic("crier", "weather", ["weather-calm"]),
  ],
};
M.jobs = [{ type: "image", status: "waiting", kind: "persona", subject: "officer_a",
  roles: ["idle"], tags: ["hungry"], nsfw: "no", count: 1, done: 0, failed: 0 }];
const tax = { kind: "persona", subjects: [], roles: Object.keys(TAX), by: "role", count: 2 };
const plan = media.recPlan(tax);
eq(plan.map(p => p.t.s), ["officer_a", "officer_a"]);
eq(plan.map(p => [p.have, p.pending, p.short]), [[1, 0, 1], [0, 1, 1]]);
assert.equal(media.recPrompts(tax, plan[1].t).prompt, "Hungry prompt");
assert.equal(media.recPlan({ ...tax, subjects: ["officer_b", "crier"] }).length, 0);
const weather = { ...tax, roles: Object.keys(WET) };
const [calm] = media.recPlan(weather);
eq([calm.have, calm.pending, calm.short], [1, 0, 1]);
const prompt = media.recPrompts(weather, calm.t);
eq(prompt.variants, ["Calm prompt", "Another angle"]);
eq(prompt.tags, ["weather", "weather-calm"]);
console.log("Clean customs and weather recipe checks passed");
