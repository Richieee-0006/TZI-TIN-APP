let FULL = [];        // všechny otázky zdroje
let ALL = [];         // po filtru typu
let recallCat = '';   // vybraná kategorie doplňovačky, '' = všechny
let RECALL = [];      // doplňovačka (type recall), napříč přednáškami, mimo FULL/ALL
let currentSource = '';
let sources = [];
let progress = {};    // {qid: "correct"|"wrong"}
let session = null;
let typeFilter = 'all';

let queue = [], idx = 0, history = [], checked = false, suddenDeath = false;
let selected = new Set(), modalMode = 'random', studyMode = false, studyPicks = [];
let examMode = false, examTimer = null, examEndTime = 0;
let kothMode = false, compMode = null, activeDuelId = null, activeRoomId = null, activeRoomData = null, roomPollTimer = null, kothStartTime = 0, kothLastResult = null;
let optOrder = {};    // q.id → zamíchané původní klíče možností, stálé po celou sadu (i po „Předchozí“)

const $ = id => document.getElementById(id);
const plural = (n, one, few, many) => { const c = WASM_CORE.exp.pluralCategory(n | 0); return c === 0 ? one : (c === 1 ? few : many); };
const show = id => {
  for (const s of ['menu','chunks','chunk-detail','comp-arena','leaderboard-view','profile-view','room-lobby','quiz','results']) {
    const el = $(s);
    if (el) el.style.display = (s === id) ? 'block' : 'none';
  }
};
const norm = s => {
  const l = WASM_CORE.writeStr(1024, String(s || '').normalize('NFC'));
  const outLen = WASM_CORE.exp.normInput(1024, l, 5120);
  return WASM_CORE.readStr(5120, outLen);
};
const isRecall = q => q.type === 'recall';
const isInput = q => q.type === 'input' || isRecall(q); // recall = psaná odpověď z paměti
const isReveal = q => q.reveal === true; // zadání bez políčka, řešení se jen odhalí
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const shuffle = a => {
  a = [...a];
  if (a.length <= 1) return a;
  const seed = ((Math.random() * 0xFFFFFFFF) >>> 0) || 1;
  WASM_CORE.exp.shuffleIndices(a.length, seed);
  const idxView = new Int32Array(WASM_CORE.exp.memory.buffer, 512, a.length);
  const res = new Array(a.length);
  for (let i = 0; i < a.length; i++) res[i] = a[idxView[i]];
  return res;
}; // Fisher-Yates (100% WASM)
// Možnosti se zobrazují zamíchané, ale všude uvnitř (selected, history, id opt-*) zůstávají původní klíče.
const LETTERS = 'ABCDEFGH';
const letters = (q, keys) => keys.map(k => LETTERS[optOrder[q.id].indexOf(k)]).sort().join(', ');

