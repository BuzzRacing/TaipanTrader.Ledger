"use strict";
// The tax-desk and weather recipes in Admin > Media Library > Recipes: each recipe role is one exact picture
// (role + tags), counted that way, and queued with the same role and tags the .bat files used.

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

const entry = (role, need, not, tags, nsfw, clean, variants) => ({ nsfw, clean, aspect: "3:4", role, need, not, tags, label: "x", variants });
const TAX = {
  tax_entry_sly: entry("sly", ["sly"], [], ["sly"], "N-sly", "C-sly"),
  tax_entry_hungry: entry("idle", ["hungry"], [], ["hungry"], "N-hungry", "C-hungry"),
};
const WET = {
  weather_nude_calm: entry("weather", ["weather-calm"], ["topless"], ["weather", "weather-calm"], "N1", "", { nsfw: ["N1", "N2", "N3", "N4"], clean: [] }),
  weather_topless_calm: entry("weather", ["weather-calm", "topless"], [], ["weather", "weather-calm", "topless"], "T1", "", { nsfw: ["T1", "T2"], clean: [] }),
  weather_clean_calm: entry("weather", ["weather-calm"], [], ["weather", "weather-calm"], "", "C1", { nsfw: [], clean: ["C1", "C2"] }),
};
const pic = (subject, roles, tags, nsfw) => ({ id: "m" + Math.random(), type: "image", kind: "persona", subject, roles, tags, nsfw, enabled: true, missing: false, url: "/media/x.png", prompt: "p" });

M.lib = {
  kinds: { persona: { label: "Personas", one: "Persona", roles: [["sly", "Sly"], ["idle", "Idle"], ["weather", "Weather"]] } },
  subjects: { persona: [["officer_a", "A"], ["officer_b", "B"], ["crier", "Tilly"]] },
  scene_prompts: { officer_a: TAX, crier: WET },
  virtual_roles: { tax_entry_sly: "Desk face, sly", tax_entry_hungry: "Desk face, hungry", weather_nude_calm: "Weather calm, nude", weather_topless_calm: "Weather calm, topless", weather_clean_calm: "Weather calm, clean" },
  items: [
    pic("officer_a", ["sly"], ["sly"], true),                                  // her sly desk face, NSFW
    pic("officer_a", ["idle"], ["bored"], true),                               // an idle picture that is not the hungry tell
    pic("crier", ["weather"], ["weather", "weather-calm"], true),              // the nude weather picture (Crimson tags it no more than this)
    pic("crier", ["weather"], ["weather", "weather-calm", "topless"], true),   // a topless one: not a nude
    pic("crier", ["weather"], ["weather", "weather-calm", "clean"], false),    // a clean one
  ],
};
M.jobs = [{ type: "image", status: "waiting", kind: "persona", subject: "officer_a", roles: ["idle"], tags: ["hungry"], nsfw: "yes", count: 1, done: 0, failed: 0 }];
M.recipes = [];

const tax = { kind: "persona", subjects: [], roles: ["tax_entry_sly", "tax_entry_hungry"], by: "role", mode: "pairs", clean: 1, nsfw: 1, count: 1, mood: "", pose: false };
const plan = media.recPlan(tax);
eq(plan.map(p => p.t.s), ["officer_a", "officer_a"], "only an officer with prompts gets a target");
const by = Object.fromEntries(plan.map(p => [p.t.role, p]));
eq([by.tax_entry_sly.haveN, by.tax_entry_sly.needN, by.tax_entry_sly.needC], [1, 0, 1], "her sly desk face counts");
eq([by.tax_entry_hungry.haveN, by.tax_entry_hungry.pendN, by.tax_entry_hungry.needN, by.tax_entry_hungry.needC], [0, 1, 0, 1], "an idle picture without the hungry tag is not the hungry tell; a queued one is on its way");
const made = media.recPrompts(tax, by.tax_entry_hungry.t);
assert.equal(made.nsfwP, "N-hungry");
assert.equal(made.cleanP, "C-hungry");
assert.equal(made.aspect, "3:4");
eq(made.tags, ["hungry"]);

const nude = media.recPlan({ kind: "persona", subjects: ["crier"], roles: ["weather_nude_calm"], by: "role", mode: "pairs", clean: 0, nsfw: 4, count: 1, mood: "", pose: true });
eq([nude[0].haveN, nude[0].needN, nude[0].needC], [1, 3, 0], "a nude weather picture counts; the topless and the clean one do not");
const top = media.recPlan({ kind: "persona", subjects: ["crier"], roles: ["weather_topless_calm"], by: "role", mode: "pairs", clean: 0, nsfw: 2, count: 1, mood: "", pose: true });
eq([top[0].haveN, top[0].needN], [1, 1], "only the topless one counts as topless");
const clean = media.recPlan({ kind: "persona", subjects: ["crier"], roles: ["weather_clean_calm"], by: "role", mode: "pairs", clean: 2, nsfw: 0, count: 1, mood: "", pose: true });
eq([clean[0].haveC, clean[0].needC, clean[0].needN], [1, 1, 0], "the clean weather picture counts for the clean role");
const vp = media.recPrompts({ kind: "persona", pose: true }, nude[0].t);
eq(vp.variants.nsfw, ["N1", "N2", "N3", "N4"], "one prompt per pose");
eq(vp.tags, ["weather", "weather-calm"]);
assert.equal(vp.fixed, true);

// A recipe with a virtual role never reaches a woman who has no prompt for it.
assert.equal(media.recPlan(Object.assign({}, tax, { subjects: ["officer_b", "crier"] })).length, 0);
console.log("tax desk and weather recipes: counted by role and tags, queued with the .bat files' tags");
