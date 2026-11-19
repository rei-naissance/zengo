"use strict";
document.querySelectorAll("[data-i]").forEach((el) => el.replaceWith(icon(el.dataset.i)));
$("refreshModels").append(icon("refresh"));

function toast(msg, ms = 1800) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), ms);
}

// ---- navigation --------------------------------------------------------------
const loaders = { history: loadHistory, saved: loadSaved, settings: loadSettings };
function go(view) {
  document.querySelectorAll(".nav").forEach((b) => b.classList.toggle("on", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("hidden", v.id !== "view-" + view));
  loaders[view]?.();
  if (view === "translate") $("text").focus();
}
document.querySelectorAll(".nav").forEach((b) => (b.onclick = () => go(b.dataset.view)));

// ---- translate ---------------------------------------------------------------
const view = new ResultView($("result"), {
  win: "main", compact: false, showSourceForLatin: false,
  onNeedsKey: () => go("settings"),
  // DeepL counts characters a moment after the request; refresh the quota shortly after.
  onTranslated: () => { clearTimeout(usageTimer); usageTimer = setTimeout(() => refreshUsage(true), 3000); },
});
let usageTimer;
const ta = $("text");
let lastTranslated = "";
// The box grows while you edit, and shrinks back once you look at the result so long text
// doesn't push the translation below the fold.
function autosize() {
  const cap = document.activeElement === ta ? 260 : 112;
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, cap) + "px";
}
ta.addEventListener("focus", autosize);
ta.addEventListener("blur", autosize);
function updateMeta() { $("chars").textContent = ta.value.trim() ? `${ta.value.length} chars` : ""; }

function run(translate = true, opts = {}) {
  const text = ta.value.trim();
  if (!text) return;
  if (translate) lastTranslated = text;
  view.load(text, { translate, record: true, ...opts });
}
let typingTimer;
ta.addEventListener("input", () => {
  autosize(); updateMeta();
  clearTimeout(typingTimer);
  // live local breakdown while typing; DeepL only on Ctrl+Enter / paste (saves quota)
  typingTimer = setTimeout(() => ta.value.trim() && ta.value.trim() !== lastTranslated && run(false), 350);
});
ta.addEventListener("paste", () => setTimeout(() => { clearTimeout(typingTimer); run(true); }, 0));
ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.ctrlKey) { e.preventDefault(); run(true); } });
$("go").onclick = () => run(true);
$("clear").onclick = () => { ta.value = ""; autosize(); updateMeta(); $("result").classList.add("hidden"); ta.focus(); };
$("furi").onclick = () => { Config.furigana = !Config.furigana; paintPrefs(); api("set_pref", "furigana", Config.furigana); };

zengo.openText = (text, translation) => {
  go("translate");
  ta.value = text; ta.blur(); autosize(); updateMeta();
  lastTranslated = text;
  view.load(text, translation ? { translation } : { record: false });
};
zengo.openView = (name) => go(name);

// ---- history -------------------------------------------------------------------
function dayLabel(ts) {
  const d = new Date(ts * 1000), now = new Date();
  const diff = Math.floor((new Date(now.toDateString()) - new Date(d.toDateString())) / 864e5);
  return diff === 0 ? "Today" : diff === 1 ? "Yesterday" : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: d.getFullYear() === now.getFullYear() ? undefined : "numeric" });
}
async function loadHistory() {
  const rows = await api("history_list", $("hq").value.trim());
  const out = [];
  let lastDay = null;
  for (const r of rows) {
    const day = dayLabel(r.ts);
    if (day !== lastDay) { out.push(h("div", { class: "day" }, day)); lastDay = day; }
    const del = h("button", { class: "ibtn", title: "Delete from history", "aria-label": "Delete from history" }, icon("trash"));
    del.onclick = async (e) => { e.stopPropagation(); await api("history_delete", r.id); loadHistory(); };
    out.push(h("div", { class: "hrow", tabindex: "0", onclick: () => zengo.openText(r.text, r.translation),
      onkeydown: (e) => { if (e.key === "Enter") zengo.openText(r.text, r.translation); } },
      h("div", { class: r.ja ? "src" : "src latin" }, r.text),
      h("div", { class: r.ja ? "tr" : "tr jpx" }, r.translation),
      h("div", { class: "when" }, new Date(r.ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), del)));
  }
  $("hlist").replaceChildren(...(out.length ? out : [h("div", { class: "empty" }, "Nothing yet. Everything you translate shows up here.")]));
}
let hTimer;
$("hq").oninput = () => { clearTimeout(hTimer); hTimer = setTimeout(loadHistory, 200); };
$("hclear").onclick = async () => { if (confirm("Delete all history?")) { await api("history_clear"); loadHistory(); } };

// ---- saved words ----------------------------------------------------------------
async function loadSaved() {
  const rows = await api("saved_list", $("sq").value.trim());
  $("savedCount").textContent = $("sq").value.trim() ? "" : rows.length || "";
  if (!rows.length) {
    $("slist").replaceChildren(h("div", { class: "empty" }, $("sq").value.trim()
      ? "No saved words match that search."
      : "Nothing saved yet. Use the star next to any word in a breakdown to keep it here."));
    return;
  }
  const date = (ts) => new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  $("slist").replaceChildren(h("table", { class: "saved" },
    h("thead", {}, h("tr", {}, ["Word", "Meaning", "Seen in", "Saved", ""].map((t) => h("th", {}, t)))),
    h("tbody", {}, rows.map((r) => {
      const del = h("button", { class: "ibtn", title: `Remove ${r.word}`, "aria-label": `Remove ${r.word}` }, icon("trash"));
      del.onclick = () => api("unsave_word", r.word);
      return h("tr", {},
        h("td", {}, h("span", { class: "word" }, rubyNodes(r.segs.length ? r.segs : [{ t: r.word }])), h("span", { class: "pos" }, r.pos)),
        h("td", { class: "mean" }, r.meaning),
        h("td", {}, r.sentence ? h("div", { class: "sent", title: `Open: ${r.sentence}`, onclick: () => zengo.openText(r.sentence) }, r.sentence) : null),
        h("td", { class: "date" }, date(r.ts)),
        h("td", {}, del));
    }))));
}
let sTimer;
$("sq").oninput = () => { clearTimeout(sTimer); sTimer = setTimeout(loadSaved, 200); };
$("export").onclick = async () => { const p = await api("export_saved"); if (p) toast("Exported to " + p); };
zengo.onSavedChanged = async () => {
  await Saved.refresh();
  if (!$("view-saved").classList.contains("hidden")) loadSaved();
  else $("savedCount").textContent = Saved.words.size || "";
};

// ---- settings --------------------------------------------------------------------
const FIELDS = ["deepl_key", "ollama_key", "ollama_model", "en_variant", "ja_formality", "auto_explain",
  "hotkey_enabled", "double_copy_ms", "autostart", "history_enabled", "theme"];

async function loadModels(selected) {
  const sel = $("ollama_model");
  const r = await api("ollama_models");
  const models = r.models || [];
  if (selected && !models.includes(selected)) models.unshift(selected);
  models.sort((a, b) => (/flash/.test(b) - /flash/.test(a)) || a.localeCompare(b));
  sel.replaceChildren(...models.map((m) => h("option", { value: m }, m)));
  sel.value = selected;
  return r;
}

// ---- key status + usage: fetched automatically, no need to press Check ----------------
function setStatus(el, cls, text) { el.className = "status" + (cls ? " " + cls : ""); el.textContent = text; }
const fmt = (n) => n.toLocaleString();

function paintUsage(u) {
  const rail = $("railUsage");
  if (!u || u.error || !u.limit) {
    $("usageField").classList.add("hidden");
    rail.textContent = ""; rail.title = "";
    return;
  }
  const pct = Math.min(100, (u.used / u.limit) * 100);
  const left = Math.max(0, u.limit - u.used);
  $("usageField").classList.remove("hidden");
  $("usageBar").style.width = pct + "%";
  const m = $("usageMeter");
  m.classList.toggle("warn", pct >= 80 && pct < 100);
  m.classList.toggle("full", pct >= 100);
  m.setAttribute("aria-valuenow", Math.round(pct));
  setStatus($("usageText"), pct >= 100 ? "bad" : "",
    `${fmt(u.used)} / ${fmt(u.limit)} characters · ${fmt(left)} left`);
  $("usagePlan").textContent = (u.free ? "DeepL API Free" : "DeepL API Pro") + " · updates automatically";
  rail.textContent = `${pct < 1 && pct > 0 ? "<1" : Math.round(pct)}%`;
  rail.title = `${fmt(u.used)} of ${fmt(u.limit)} characters used this month`;
  rail.classList.toggle("warn", pct >= 80);
}

let usageAt = 0, usageBusy = null;
/** Fetch DeepL usage; `fresh` skips both caches (ours here and the 20 s one in Python). */
function refreshUsage(fresh = false) {
  if (!Config.has_deepl) { paintUsage(null); setStatus($("deeplStatus"), "", ""); return Promise.resolve(); }
  if (!fresh && Date.now() - usageAt < 30_000) return Promise.resolve();
  if (usageBusy) return usageBusy;
  usageBusy = (async () => {
    const u = await api("deepl_usage", fresh);
    usageAt = Date.now();
    paintUsage(u);
    if (u.error) setStatus($("deeplStatus"), "bad", u.error);
    else setStatus($("deeplStatus"), "ok", "Connected");
  })().finally(() => (usageBusy = null));
  return usageBusy;
}

function paintAiStatus(r) {
  if (!Config.has_ollama) setStatus($("aiStatus"), "", "");
  else if (r.error) setStatus($("aiStatus"), "bad", r.error);
  else setStatus($("aiStatus"), "ok", `Connected · ${r.models.length} models`);
}
async function loadSettings() {
  const c = await api("settings_get");
  Object.assign(Config, c);
  for (const f of FIELDS) {
    const el = $(f);
    if (el.type === "checkbox") el.checked = !!c[f];
    else if (f.endsWith("_key")) { el.value = ""; el.placeholder = c[f] ? `Saved (${c[f]})` : "Paste your key"; }
    else if (f !== "ollama_model") el.value = c[f];
  }
  if (Config.has_ollama) setStatus($("aiStatus"), "", "Checking…");
  loadModels(c.ollama_model).then(paintAiStatus);
  refreshUsage(true);
  checkUpdates(false);
  $("saveStatus").textContent = "";
}

// ---- about / updates ------------------------------------------------------------------
let updateCheckedAt = 0;
async function checkUpdates(manual) {
  // Opening Settings checks at most every 30 minutes; the button always checks.
  if ($("checkUpdate").disabled || (!manual && Date.now() - updateCheckedAt < 30 * 60_000)) return;
  updateCheckedAt = Date.now();
  const s = $("updateStatus"), list = $("updateChanges"), apply = $("applyUpdate");
  setStatus(s, "", "Checking…");
  const r = await api("update_check");
  apply.classList.add("hidden");
  list.classList.add("hidden");
  if (r.error) { setStatus(s, manual ? "bad" : "", r.error); return; }
  if (!r.behind) {
    setStatus(s, "ok", r.ahead ? `Up to date (${r.ahead} local commit${r.ahead > 1 ? "s" : ""} not on GitHub)` : "You have the latest version");
    return;
  }
  setStatus(s, "", `${r.behind} update${r.behind > 1 ? "s" : ""} available` + (r.dirty ? " · you have local edits; they're kept if they don't clash" : ""));
  list.replaceChildren(...r.changes.map((c) => h("li", {}, c)));
  list.classList.toggle("hidden", !r.changes.length);
  apply.classList.remove("hidden");
}
$("checkUpdate").onclick = () => checkUpdates(true);
$("applyUpdate").onclick = async () => {
  if (!confirm("Zengo will close, update in a console window, and start again. Continue?")) return;
  const r = await api("update_apply");
  if (r.error) setStatus($("updateStatus"), "bad", r.error);
  else setStatus($("updateStatus"), "", "Updating… Zengo will restart in a moment.");
};
async function loadAbout() {
  const a = await api("app_info");
  $("aboutVersion").textContent = `Zengo ${a.version}`;
  $("aboutFolder").textContent = a.folder;
  $("aboutDict").textContent = a.dict_date ? `· dictionary ${a.dict_date}` : "";
  if (!a.git) { $("checkUpdate").disabled = true; setStatus($("updateStatus"), "", "Not a git install: download new versions by hand and run setup.bat"); }
  return a;
}
$("refreshUsage").append(icon("refresh"));
$("refreshUsage").onclick = () => refreshUsage(true);
$("refreshModels").onclick = () => loadModels($("ollama_model").value);

function collect() {
  const v = {};
  for (const f of FIELDS) {
    const el = $(f);
    if (el.type === "checkbox") v[f] = el.checked;
    else if (el.type === "number") v[f] = parseInt(el.value, 10) || 500;
    else if (f.endsWith("_key")) { if (el.value.trim()) v[f] = el.value.trim(); }
    else v[f] = el.value;
  }
  return v;
}
async function save(quiet) {
  const c = await api("settings_save", collect());
  Object.assign(Config, c);
  paintPrefs();
  if (!quiet) { $("saveStatus").textContent = "Settings saved"; $("saveStatus").className = "status ok"; }
  loadSettings();
}
$("saveSettings").onclick = () => save(false);
// Checking a key saves it first; loadSettings() then re-checks both keys and the usage.
async function checkKeys(statusId) {
  setStatus($(statusId), "", "Checking…");
  await save(true);
}
$("testDeepl").onclick = () => checkKeys("deeplStatus");
$("testAi").onclick = () => checkKeys("aiStatus");
// Pasting a key is enough: it is saved and checked as soon as you leave the field or press Enter.
for (const [id, statusId] of [["deepl_key", "deeplStatus"], ["ollama_key", "aiStatus"]]) {
  $(id).addEventListener("change", () => $(id).value.trim() && checkKeys(statusId));
  $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") $(id).blur(); });
}

// ---- prefs / boot ------------------------------------------------------------------
function paintPrefs() {
  $("furi").classList.toggle("on", !!Config.furigana);
  document.body.classList.toggle("nofuri", !Config.furigana);
  $("dotDeepl").classList.toggle("ok", !!Config.has_deepl);
  $("dotAi").classList.toggle("ok", !!Config.has_ollama);
  applyTheme(Config.theme);
}
zengo.onConfig = (c) => { Object.assign(Config, c); paintPrefs(); };

(async () => {
  Object.assign(Config, await api("settings_get"));
  paintPrefs();
  await Saved.refresh();
  $("savedCount").textContent = Saved.words.size || "";
  if (!Config.has_deepl && !Config.has_ollama) go("settings");
  else ta.focus();
  refreshUsage(true);
  const about = await loadAbout();
  if (about.updated_from) toast(`Updated to Zengo ${about.version} (from ${about.updated_from})`, 5000);
})();
// Popup translations use quota too: refresh when you come back to this window.
window.addEventListener("focus", () => refreshUsage());
zengo.onUsageChanged = () => { clearTimeout(usageTimer); usageTimer = setTimeout(() => refreshUsage(true), 3000); };
