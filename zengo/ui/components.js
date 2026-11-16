/* Shared UI building blocks for the main window and the popup. */
"use strict";

// ---- python bridge ---------------------------------------------------------
const apiReady = new Promise((res) => {
  if (window.pywebview?.api) res();
  else window.addEventListener("pywebviewready", res, { once: true });
});
async function api(name, ...args) {
  await apiReady;
  return window.pywebview.api[name](...args);
}

// ---- DOM helpers -----------------------------------------------------------
const $ = (id) => document.getElementById(id);
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style") el.style.cssText = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false || kid === "") continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const ICONS = {
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  pin: '<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  star: '<path d="M11.5 2.6a.6.6 0 0 1 1 0l2.6 5.3 5.8.8a.6.6 0 0 1 .3 1l-4.2 4.1 1 5.8a.6.6 0 0 1-.8.6L12 17.5l-5.2 2.7a.6.6 0 0 1-.8-.6l1-5.8L2.8 9.7a.6.6 0 0 1 .3-1l5.8-.8z"/>',
  chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 9h8"/><path d="M8 13h5"/>',
  chevron: '<path d="m9 18 6-6-6-6"/>',
  external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  expand: '<path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/>',
  send: '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  translate: '<path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  book: '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
};
function icon(name) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor");
  s.setAttribute("stroke-width", "2");
  s.setAttribute("stroke-linecap", "round");
  s.setAttribute("stroke-linejoin", "round");
  s.innerHTML = ICONS[name];
  return s;
}

function copyButton(getText, cls = "ibtn copy") {
  const b = h("button", { class: cls, title: "Copy" }, icon("copy"));
  b.onclick = async (e) => {
    e.stopPropagation();
    try { await navigator.clipboard.writeText(getText()); } catch (_) { /* ignore */ }
    b.replaceChildren(icon("check"));
    setTimeout(() => b.replaceChildren(icon("copy")), 1000);
  };
  return b;
}

function applyTheme(theme) {
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}

// ---- markdown (tiny, escapes first) ----------------------------------------
function renderMarkdown(src) {
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const inline = (s) => esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<em>$2</em>");
  const out = [];
  let list = null, para = [];
  const flushPara = () => { if (para.length) { out.push(`<p>${para.map(inline).join("<br>")}</p>`); para = []; } };
  const flushList = () => { if (list) { out.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`); list = null; } };
  for (const raw of src.split("\n")) {
    const line = raw.trimEnd();
    let m;
    if (!line.trim()) { flushPara(); flushList(); continue; }
    if ((m = line.match(/^\s*(#{1,6})\s+(.*)$/))) { flushPara(); flushList(); out.push(`<h3>${inline(m[2])}</h3>`); continue; }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { flushPara(); flushList(); continue; }
    if ((m = line.match(/^\s*[-*•]\s+(.*)$/)) || (m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
      flushPara();
      const tag = /^\s*\d/.test(line) ? "ol" : "ul";
      if (!list || list.tag !== tag) { flushList(); list = { tag, items: [] }; }
      list.items.push(m[1]);
      continue;
    }
    if ((m = line.match(/^\s*>\s?(.*)$/))) { flushPara(); flushList(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); continue; }
    if (list && /^\s{2,}/.test(raw)) { list.items[list.items.length - 1] += " " + line.trim(); continue; }
    flushList();
    para.push(line);
  }
  flushPara(); flushList();
  return out.join("");
}

// ---- word display ------------------------------------------------------------
const POS_COLOR = {
  "noun": "var(--noun)", "pronoun": "var(--noun)", "verb": "var(--verb)",
  "i-adjective": "var(--adj)", "na-adjective": "var(--adj)", "adverb": "var(--adv)",
  "particle": "var(--particle)", "auxiliary": "var(--infl)",
};
const JLPT = { 4: "N5", 3: "N4", 2: "N3–N2", 1: "N1" };

function rubyNodes(segs) {
  return segs.map((s) => s.r ? h("ruby", {}, s.t, h("rt", {}, s.r)) : document.createTextNode(s.t));
}

function senseList(senses, max) {
  return h("ol", { class: "senses" }, senses.slice(0, max).map((s, i) => {
    const posText = s.pos.join(", ");
    const prev = i > 0 ? senses[i - 1].pos.join(", ") : null;
    return h("li", {},
      posText && posText !== prev ? h("span", { class: "sp" }, posText) : null,
      s.glosses.join("; "),
      [...s.misc, ...s.field, ...s.dialect].map((m) => h("span", { class: "chip misc" }, m)),
      s.info.length ? h("span", { class: "chip" }, s.info.join("; ")) : null,
    );
  }));
}

function kanjiTile(k) {
  return h("div", { class: "kanji" },
    h("span", { class: "g" }, k.literal),
    h("span", { class: "m" }, k.m.slice(0, 4).join(", ") || "—"),
    k.on.length ? h("span", { class: "rd" }, h("i", {}, "音"), k.on.slice(0, 4).join("・")) : h("span"),
    k.kun.length ? h("span", { class: "rd" }, h("i", {}, "訓"), k.kun.slice(0, 4).join("・")) : h("span"),
    h("span", { class: "meta" }, [
      k.strokes && `${k.strokes} strokes`,
      k.grade && (k.grade <= 6 ? `grade ${k.grade}` : k.grade === 8 ? "jōyō (secondary)" : "jinmeiyō"),
      k.jlpt && `JLPT ≈ ${JLPT[k.jlpt]}`,
      k.freq && `freq #${k.freq}`,
    ].filter(Boolean).join(" · ")),
  );
}

// Saved-word state shared by every card on the page.
const Saved = {
  words: new Set(),
  async refresh() { this.words = new Set(await api("saved_set")); this.paint(); },
  paint() {
    document.querySelectorAll(".star[data-word]").forEach((b) => b.classList.toggle("on", this.words.has(b.dataset.word)));
  },
};

function starButton(w, sentence) {
  const e = w.entries?.[0];
  const word = w.base || w.surface;
  const b = h("button", { class: "ibtn star", title: "Save to word list", "data-word": word }, icon("star"));
  b.classList.toggle("on", Saved.words.has(word));
  b.onclick = async (ev) => {
    ev.stopPropagation();
    if (Saved.words.has(word)) {
      Saved.words.delete(word);
      Saved.paint();
      await api("unsave_word", word);
    } else {
      Saved.words.add(word);
      Saved.paint();
      await api("save_word", {
        word, reading: w.base_reading || e?.reading || w.reading,
        meaning: (e?.senses || []).slice(0, 3).map((s) => s.glosses.slice(0, 3).join(", ")).join("; "),
        pos: w.vclass || w.pos, sentence,
      });
    }
  };
  return b;
}

function jishoLink(q) {
  return h("button", { class: "ibtn", title: `Look up ${q} on jisho.org`, "aria-label": `Look up ${q} on jisho.org`,
    onclick: () => api("open_url", "https://jisho.org/search/" + encodeURIComponent(q)) }, icon("external"));
}

const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

function settingsLink(onClick) {
  return h("button", { class: "link", onclick: () => onClick?.() }, "Add it in Settings");
}

function wordCard(w, sentence) {
  if (w.kind === "particle" && w.grammar) {
    return h("div", { class: "entry particle", "data-card": w.i },
      h("span", { class: "word" }, w.surface),
      h("div", {},
        h("span", { class: "gl" }, w.grammar.label), " ",
        h("span", { class: "nt" }, w.grammar.note),
        w.parts?.length ? h("div", { class: "chain" }, w.parts.map((p) => h("span", { class: "step", title: p.note }, p.t ? h("b", {}, p.t) : null, p.label))) : null,
      ));
  }
  const e = w.entries?.[0];
  const card = h("div", { class: "entry", "data-card": w.i });
  card.style.setProperty("--pc", POS_COLOR[w.pos] || "var(--muted)");
  // Kana-only words written differently in the dictionary (e.g. わかる → 分かる): show the usual spelling.
  const spelling = !w.parts?.length && e && e.head !== w.surface && !w.segs.some((s) => s.r)
    ? h("span", { class: "reading" }, `usually ${e.head}`) : null;
  card.append(h("div", { class: "top" },
    h("span", { class: "word" }, rubyNodes(w.segs)),
    spelling,
    h("span", { class: "pos" }, w.vclass || w.pos),
    e?.common ? h("span", { class: "chip", title: "Marked as a common word in JMdict" }, "common") : null,
    h("span", { class: "acts" }, jishoLink(w.base || w.surface), e ? starButton(w, sentence) : null),
  ));
  if (w.parts?.length) {
    const baseLabel = w.base_reading && w.base_reading !== w.base ? `${w.base}【${w.base_reading}】` : (w.base || w.surface);
    card.append(h("div", { class: "chain", "aria-label": "How this form is built" },
      h("span", { class: "step base" }, h("b", {}, baseLabel), "dictionary form"),
      w.parts.map((p) => [icon("chevron"), h("span", { class: "step", title: p.note }, p.t ? h("b", {}, p.t) : null, p.label)]),
    ));
  }
  if (w.grammar && w.kind === "aux") {
    card.append(h("div", { style: "color:var(--muted)" }, `${w.grammar.label} — ${w.grammar.note}`));
  }
  if (e) {
    card.append(senseList(e.senses, 4));
    const extras = [];
    if (e.senses.length > 4) extras.push(senseList(e.senses.slice(4), 10));
    if (e.other_forms.length) extras.push(h("div", { class: "alt" }, "Other spellings: ", h("span", { class: "jp" }, e.other_forms.join("、"))));
    for (const alt of w.entries.slice(1)) {
      extras.push(h("div", { class: "alt" }, h("span", { class: "jp" }, `${alt.head}【${alt.reading}】`), " — ",
        alt.senses.slice(0, 2).map((s) => s.glosses.slice(0, 3).join("; ")).join(" / ")));
    }
    if (extras.length) card.append(h("details", { class: "more" }, h("summary", {}, "more meanings"), extras));
  } else if (!w.grammar) {
    card.append(h("div", { class: "empty" }, "Not in the dictionary. It may be a name, slang, or a compound the tokenizer split."));
  }
  return card;
}

// ---- AI streaming dispatch -----------------------------------------------
const AI = { handlers: new Map(), seq: Date.now() % 1e6 };
window.zengo = window.zengo || {};
zengo.aiChunk = (rid, text) => AI.handlers.get(rid)?.chunk(text);
zengo.aiDone = (rid) => { AI.handlers.get(rid)?.done(); AI.handlers.delete(rid); };
zengo.aiError = (rid, msg) => { AI.handlers.get(rid)?.error(msg); AI.handlers.delete(rid); };
zengo.onSavedChanged = () => Saved.refresh();

class AiPanel {
  constructor(winName, { detail, getContext, onNeedsKey }) {
    this.win = winName;
    this.detail = detail;
    this.getContext = getContext;       // async () => ({text, translation})
    this.onNeedsKey = onNeedsKey;
    this.el = h("div", { class: "ai" });
    this.reset();
  }
  reset() {
    this.started = false;
    this.busy = false;
    this.transcript = [];
    api("cancel_ai", this.win);
    this.el.replaceChildren(h("div", { class: "ai-empty" },
      h("p", {}, "An AI tutor explains the tone, implied meaning and grammar of this sentence, and where the translation falls short. You can ask follow-up questions."),
      h("button", { class: "btn", onclick: () => this.start() }, icon("chat"), "Explain this sentence")));
  }
  _frame() {
    this.out = h("div", { class: "md", "aria-live": "polite" });
    this.state = h("span", { class: "state" });
    this.input = h("input", { placeholder: "Ask a follow-up, e.g. why が and not は here?", "aria-label": "Follow-up question", onkeydown: (e) => { if (e.key === "Enter") this.ask(); } });
    this.sendBtn = h("button", { class: "btn", title: "Ask", onclick: () => this.ask() }, icon("send"), "Ask");
    this.el.replaceChildren(
      h("div", { class: "ai-head" }, h("span", { class: "model" }, Config.ollama_model || "AI"),
        h("span", {}, "on Ollama Cloud"), this.state, h("span", { class: "spacer" }),
        h("button", { class: "ibtn", title: "Explain again", "aria-label": "Explain again", onclick: () => this.start() }, icon("refresh")),
        copyButton(() => this.transcript.map((t) => (t.q ? `Q: ${t.q}\n\n` : "") + t.text).join("\n\n"), "ibtn")),
      this.out, h("div", { class: "ask" }, this.input, this.sendBtn));
  }
  async start() {
    if (!Config.has_ollama) {
      this.el.replaceChildren(h("div", { class: "ai-empty" },
        h("p", {}, "AI explanations need an Ollama Cloud key. ", settingsLink(this.onNeedsKey))));
      return;
    }
    this.started = true;
    this._frame();
    this.transcript = [];
    const ctx = await this.getContext();
    this._run((rid) => api("explain", this.win, rid, ctx.text, ctx.translation || null, this.detail), null);
  }
  ask() {
    const q = this.input.value.trim();
    if (!q || this.busy) return;
    this.input.value = "";
    this._run((rid) => api("ask", this.win, rid, q), q);
  }
  _run(call, question) {
    const rid = ++AI.seq;
    this.busy = true;
    this.sendBtn.disabled = true;
    const entry = { q: question, text: "" };
    this.transcript.push(entry);
    if (question) this.out.append(h("div", { class: "q" }, question));
    const target = h("div", {}, h("div", { class: "shimmer", style: "width:70%" }), h("div", { class: "shimmer", style: "width:45%" }));
    this.out.append(target);
    this.state.textContent = "· writing…";
    const finish = () => { this.busy = false; this.sendBtn.disabled = false; this.state.textContent = ""; };
    AI.handlers.set(rid, {
      chunk: (t) => { entry.text += t; target.innerHTML = renderMarkdown(entry.text); },
      done: () => { finish(); if (!entry.text) target.textContent = "(empty response)"; },
      error: (m) => { finish(); target.replaceChildren(h("span", { class: "err" }, m)); },
    });
    call(rid).catch((e) => AI.handlers.get(rid)?.error(String(e?.message || e)));
  }
}

// ---- the full result (sentence, translation, breakdown, AI) --------------
const Config = {};
class ResultView {
  constructor(root, { win, compact, showSourceForLatin = true, onNeedsKey }) {
    this.win = win;
    this.compact = compact;
    this.showSourceForLatin = showSourceForLatin;
    this.onNeedsKey = onNeedsKey;
    this.seq = 0;
    this.ai = new AiPanel(win, {
      detail: compact ? "brief" : "full",
      getContext: async () => ({ text: this.text, translation: (await this.translationPromise)?.text }),
      onNeedsKey,
    });
    this.els = {
      srcWrap: h("div", {}, h("div", { class: "source", role: "region", "aria-label": "Original text" })),
      trWrap: h("div", {}, h("div", { class: "translation", role: "region", "aria-label": "Translation" })),
      notes: h("div", { class: "notes" }),
      tabs: h("div", { class: "tabs" }),
      words: h("div", { class: "words" }),
      kanji: h("div", { class: "hidden" }),
      aiTab: h("div", { class: "hidden" }, this.ai.el),
    };
    this.els.source = this.els.srcWrap.lastChild;
    this.els.trans = this.els.trWrap.lastChild;
    this.tabBtns = {
      words: h("button", { class: "tab on", onclick: () => this.showTab("words") }, "Words", h("span", { class: "n" })),
      kanji: h("button", { class: "tab", onclick: () => this.showTab("kanji") }, "Kanji", h("span", { class: "n" })),
      ai: h("button", { class: "tab", onclick: () => this.showTab("ai") }, icon("chat"), "Explain"),
    };
    this.els.tabs.append(...Object.values(this.tabBtns));
    root.replaceChildren(this.els.srcWrap, this.els.trWrap, this.els.notes, this.els.tabs, this.els.words, this.els.kanji, this.els.aiTab);
    this.root = root;
    root.classList.add("hidden");
  }

  showTab(name) {
    for (const [k, b] of Object.entries(this.tabBtns)) b.classList.toggle("on", k === name);
    this.els.words.classList.toggle("hidden", name !== "words");
    this.els.kanji.classList.toggle("hidden", name !== "kanji");
    this.els.aiTab.classList.toggle("hidden", name !== "ai");
    if (name === "ai" && !this.ai.started && Config.has_ollama) this.ai.start();
  }

  focusCard(i) {
    this.showTab("words");
    const c = this.els.words.querySelector(`[data-card="${i}"]`);
    if (!c) return;
    c.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "center" });
    c.classList.add("flash");
    setTimeout(() => c.classList.remove("flash"), 1100);
  }

  sentence(words) {
    return words.map((w) => {
      if (w.kind === "symbol") return document.createTextNode(w.surface);
      const gloss = w.grammar?.label || w.entries?.[0]?.senses?.[0]?.glosses?.slice(0, 3).join("; ") || "";
      const el = h("span", { class: `w k-${w.kind}`, title: gloss, onclick: () => this.focusCard(w.i) }, rubyNodes(w.segs));
      el.style.setProperty("--pc", POS_COLOR[w.pos] || "var(--ink)");
      return el;
    });
  }

  renderBreakdown(a, sentenceText) {
    const words = a.words.filter((w) => w.kind !== "symbol");
    this.tabBtns.words.lastChild.textContent = words.length;
    this.tabBtns.kanji.lastChild.textContent = a.kanji.length;
    this.els.words.replaceChildren(...words.map((w) => wordCard(w, sentenceText)),
      a.truncated ? h("div", { class: "empty" }, "Long text: breakdown truncated.") : "");
    this.els.kanji.replaceChildren(a.kanji.length ? h("div", { class: "kgrid" }, a.kanji.map(kanjiTile)) : h("div", { class: "empty" }, "No kanji."));
    this.els.notes.replaceChildren(...a.notes.map((n) => h("span", { class: "chip" }, n)));
  }

  /** opts: {translate: bool, record: bool, translation: string|null} */
  async load(text, opts = {}) {
    const id = ++this.seq;
    this.text = text;
    this.root.classList.remove("hidden");
    this.ai.reset();
    this.showTab("words");
    const { ja, analysis } = await api("analyze", text);
    if (id !== this.seq) return;
    this.ja = ja;
    document.querySelectorAll("[data-dir]").forEach((el) => (el.textContent = ja ? "日本語 → English" : "English → 日本語"));
    this.els.srcWrap.classList.toggle("hidden", !ja && !this.showSourceForLatin);
    this.els.source.className = "source" + (ja ? "" : " latin");
    this.els.source.replaceChildren(...(analysis ? this.sentence(analysis.words) : [document.createTextNode(text)]));
    this.els.trans.className = "translation" + (ja ? "" : " jp");
    this.els.notes.replaceChildren();
    if (analysis) this.renderBreakdown(analysis, text);
    else {
      this.els.words.replaceChildren(h("div", { class: "empty" }, "The breakdown of the Japanese translation will appear here."));
      this.els.kanji.replaceChildren();
    }

    if (opts.translation) {
      this.translationPromise = Promise.resolve({ text: opts.translation, target: ja ? "EN" : "JA" });
      if (!ja) this.translationPromise = api("translate", text, false); // EN->JA: need analysis of output (cached by DeepL client)
    } else if (opts.translate === false) {
      this.translationPromise = Promise.resolve(null);
    } else {
      this.translationPromise = api("translate", text, opts.record !== false);
    }
    const tr = this.els.trans;
    if (opts.translate === false && !opts.translation) {
      tr.replaceChildren(h("span", { style: "color:var(--faint)" }, "Press Ctrl+Enter to translate"));
    } else {
      tr.replaceChildren(h("div", { class: "shimmer", style: "width:85%" }), h("div", { class: "shimmer", style: "width:55%" }));
    }
    const r = opts.translation && ja ? { text: opts.translation } : await this.translationPromise;
    if (id !== this.seq || !r) return;
    if (r.error) {
      tr.replaceChildren(Config.has_deepl
        ? h("span", { class: "err" }, r.error)
        : h("span", {}, "Translation needs a DeepL key. ", settingsLink(this.onNeedsKey)));
      return;
    }
    if (r.analysis) {
      tr.replaceChildren(...this.sentence(r.analysis.words), copyButton(() => r.text));
      this.renderBreakdown(r.analysis, r.text);
    } else {
      tr.replaceChildren(r.text, copyButton(() => r.text));
    }
    if (Config.auto_explain && this.compact && Config.has_ollama) this.showTab("ai");
  }
}
