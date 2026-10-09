/* SEU platform EN/中文 toggle. Pages set window.__ZH_EN = {"中文": "English", ...}
 * before this script runs. Toggle swaps text nodes / placeholders / option
 * labels / document.title; computed report text from the server is not
 * translated (it carries source citations in zh).
 */
(function () {
  if (window.__I18N_ACTIVE__) return;
  window.__I18N_ACTIVE__ = true;
  var D = window.__ZH_EN || {};
  var REV = {};
  for (var k in D) REV[D[k]] = k;
  var mode = "zh";

  function swapText(node) {
    var t = node.nodeValue, t2;
    if (mode === "en") {
      var key = t.trim();
      if (D[key] !== undefined) {
        var lead = t.match(/^\s*/)[0], tail = t.match(/\s*$/)[0];
        node.nodeValue = lead + D[key] + tail;
      }
    } else {
      var key2 = t.trim();
      if (REV[key2] !== undefined) {
        var l2 = t.match(/^\s*/)[0], tl2 = t.match(/\s*$/)[0];
        node.nodeValue = l2 + REV[key2] + tl2;
      }
    }
  }

  function walk(root) {
    var it = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var n;
    while ((n = it.nextNode())) {
      if (n.parentElement &&
          /^(SCRIPT|STYLE|NOSCRIPT)$/.test(n.parentElement.tagName)) continue;
      swapText(n);
    }
    // inputs/options/placeholders/titles
    document.querySelectorAll("[placeholder]").forEach(function (el) {
      var d = mode === "en" ? D : REV;
      var v = el.getAttribute("placeholder");
      if (d[v] !== undefined) el.setAttribute("placeholder", d[v]);
    });
    document.querySelectorAll("option").forEach(function (el) {
      // options are text nodes already handled; also <option> label attr
      var d = mode === "en" ? D : REV;
      var v = el.getAttribute("label");
      if (v && d[v] !== undefined) el.setAttribute("label", d[v]);
    });
    if (D.__title__) {
      document.title = mode === "en" ? D.__title__ : (REV[D.__title__] = document.title, document.title);
    }
  }

  var observer = null;
  function watch(on) {
    if (observer) { observer.disconnect(); observer = null; }
    if (!on) return;
    observer = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var mu = muts[i];
        if (mu.type === "characterData") swapText(mu.target);
        for (var j = 0; j < mu.addedNodes.length; j++) {
          var n = mu.addedNodes[j];
          if (n.nodeType === 3) swapText(n);
          else if (n.nodeType === 1) walk(n);
        }
      }
    });
    observer.observe(document.body,
      { childList: true, subtree: true, characterData: true });
  }

  function apply(m) {
    mode = m;
    watch(false);          // pause while we bulk-swap, avoid re-entry
    walk(document.body);
    if (m === "en" && D.__title__) {
      if (!window.__I18N_TITLE_ZH__) window.__I18N_TITLE_ZH__ = document.title;
      document.title = D.__title__;
    } else if (window.__I18N_TITLE_ZH__) {
      document.title = window.__I18N_TITLE_ZH__;
    }
    document.documentElement.lang = m === "en" ? "en" : "zh-CN";
    btn.textContent = m === "en" ? "中" : "EN";
    try { localStorage.setItem("seu_lang", m); } catch (e) {}
    watch(m === "en");     // translate content rendered later
  }

  var btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "EN";
  btn.title = "Switch UI language 界面语言";
  btn.style.cssText =
    "position:fixed;right:14px;bottom:14px;z-index:9999;padding:6px 12px;" +
    "font:600 13px/1.2 'Segoe UI','Microsoft YaHei',sans-serif;color:#eaf6ff;" +
    "background:rgba(18,32,52,.92);border:1px solid #33506e;border-radius:16px;" +
    "cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.4)";
  btn.onclick = function () { apply(mode === "en" ? "zh" : "en"); };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      document.body.appendChild(btn);
      if ((localStorage.getItem("seu_lang") || "zh") === "en") apply("en");
    });
  } else {
    document.body.appendChild(btn);
    try {
      if (localStorage.getItem("seu_lang") === "en") apply("en");
    } catch (e) {}
  }
})();
