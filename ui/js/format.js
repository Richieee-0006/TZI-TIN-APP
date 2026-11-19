function renderLatexNode(tex, displayMode) {
  const span = document.createElement('span');
  if (typeof katex !== 'undefined' && katex && typeof katex.render === 'function') {
    const opts = { displayMode: !!displayMode, throwOnError: false };
    const isMathml = typeof document !== 'undefined' && document.documentElement && document.documentElement.dataset && document.documentElement.dataset.katexMode === 'mathml';
    if (isMathml) opts.output = 'mathml';
    try {
      katex.render(tex, span, opts);
      if (isMathml) {
        const bb = { N: 'ℕ', Z: 'ℤ', Q: 'ℚ', R: 'ℝ', C: 'ℂ' };
        span.querySelectorAll('mi[mathvariant="double-struck"]').forEach(mi => {
          const ch = bb[mi.textContent];
          if (!ch) return;
          const mt = document.createElementNS('http://www.w3.org/1998/Math/MathML', 'mtext');
          mt.setAttribute('class', 'math-bb');
          mt.textContent = ch;
          mi.replaceWith(mt);
        });
      }
      return span;
    } catch (e) {}
  }
  span.className = 'math-tex katex-fallback';
  span.dataset.display = displayMode ? '1' : '0';
  span.textContent = tex;
  return span;
}

// Zápis z banky / glosáře (LaTeX $...$, $$...$$, \(...\), \[...\] + matematické výrazy) převede na KaTeX (HTML / MathML).
function toLatexMathStr(raw) {
  let t = String(raw || '').trim();
  const cmdPlaceholders = [];
  const holdCmd = c => { cmdPlaceholders.push(c); return `\x02CMD${cmdPlaceholders.length - 1}\x02`; };

  // Wrap Czech/multi-letter words inside braces (e.g. {vstup, odchod}, {zavřeno, otevřeno}) before escaping braces, then escape all { and }
  t = t.replace(/\{([^{}\n]{1,64})\}/g, (_, inner) => {
    const safeInner = inner.replace(/(^|[^\\A-Za-z0-9_])([A-Za-záčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]{2,})(?![A-Za-z0-9_])/g,
      (__, pre, w) => `${pre}${holdCmd(`\\text{${w}}`)}`);
    return `{${safeInner}}`;
  });
  t = t.replace(/\{/g, '\\{').replace(/\}/g, '\\}');

  // Sumy a součiny: Σ_(i=1)^n a_i, Π_(i=1)^n a_i
  t = t.replace(/[Σ∑]_\(([^)]+)\)\^\(([^)]+)\)/g, (_, lo, hi) => holdCmd(`\\sum_{${toLatexMathStr(lo)}}^{${toLatexMathStr(hi)}}`));
  t = t.replace(/[Σ∑]_\(([^)]+)\)\^([A-Za-z0-9]+)/g, (_, lo, hi) => holdCmd(`\\sum_{${toLatexMathStr(lo)}}^{${hi}}`));
  t = t.replace(/[Π∏]_\(([^)]+)\)\^\(([^)]+)\)/g, (_, lo, hi) => holdCmd(`\\prod_{${toLatexMathStr(lo)}}^{${toLatexMathStr(hi)}}`));
  t = t.replace(/[Π∏]_\(([^)]+)\)\^([A-Za-z0-9]+)/g, (_, lo, hi) => holdCmd(`\\prod_{${toLatexMathStr(lo)}}^{${hi}}`));

  // Kombinační čísla (n nad k) a odmocniny √(x)
  t = t.replace(/\(([A-Za-z0-9+\-−\s]+?)\s+nad\s+([A-Za-z0-9+\-−\s?]+?)\)/g, (_, a, b) => holdCmd(`\\binom{${toLatexMathStr(a)}}{${toLatexMathStr(b)}}`));
  t = t.replace(/√\(([^)]+)\)/g, (_, x) => holdCmd(`\\sqrt{${toLatexMathStr(x)}}`));
  t = t.replace(/√([A-Za-z0-9]+)/g, (_, x) => holdCmd(`\\sqrt{${x}}`));

  // Operátory, sady čísel, řecká písmena a Kleeneho hvězdička
  t = t.replace(/−/g, '-').replace(/·/g, ' \\cdot ').replace(/…|\.{3}/g, ' \\dots ');
  t = t.replace(/≤/g, ' \\le ').replace(/≥/g, ' \\ge ').replace(/≠/g, ' \\ne ').replace(/≈/g, ' \\approx ').replace(/≡/g, ' \\equiv ');
  t = t.replace(/⊆/g, ' \\subseteq ').replace(/⊂/g, ' \\subset ').replace(/⊇/g, ' \\supseteq ').replace(/⊃/g, ' \\supset ');
  t = t.replace(/∩/g, ' \\cap ').replace(/∪/g, ' \\cup ').replace(/∈/g, ' \\in ').replace(/∉/g, ' \\notin ').replace(/∅/g, ' \\emptyset ').replace(/∖/g, ' \\setminus ');
  t = t.replace(/∧/g, ' \\land ').replace(/∨/g, ' \\lor ').replace(/¬/g, ' \\neg ').replace(/⇒\*/g, ' \\Rightarrow^{*} ').replace(/⇒/g, ' \\Rightarrow ').replace(/⇔/g, ' \\Leftrightarrow ');
  t = t.replace(/→/g, ' \\to ').replace(/←/g, ' \\leftarrow ').replace(/↔/g, ' \\leftrightarrow ').replace(/↦/g, ' \\mapsto ').replace(/∼/g, ' \\sim ');
  t = t.replace(/∀/g, ' \\forall ').replace(/∃!/g, ' \\exists! ').replace(/∃/g, ' \\exists ');
  t = t.replace(/ℕ/g, ' \\mathbb{N} ').replace(/ℤ/g, ' \\mathbb{Z} ').replace(/ℚ/g, ' \\mathbb{Q} ').replace(/ℝ/g, ' \\mathbb{R} ').replace(/ℂ/g, ' \\mathbb{C} ').replace(/𝓛/g, ' \\mathcal{L} ');
  t = t.replace(/∑/g, ' \\sum ').replace(/∏/g, ' \\prod ').replace(/Σ/g, ' \\Sigma ').replace(/Π/g, ' \\Pi ').replace(/δ/g, ' \\delta ').replace(/ε/g, ' \\varepsilon ').replace(/λ/g, ' \\lambda ').replace(/π/g, ' \\pi ').replace(/α/g, ' \\alpha ').replace(/β/g, ' \\beta ').replace(/γ/g, ' \\gamma ').replace(/φ/g, ' \\varphi ');
  t = t.replace(/ᵢ/g, '_i').replace(/ⱼ/g, '_j').replace(/ₖ/g, '_k').replace(/ₙ/g, '_n').replace(/′/g, "'");
  t = t.replace(/[₀-₉]+/g, m => '_{' + [...m].map(c => '₀₁₂₃₄₅₆₇₈₉'.indexOf(c)).join('') + '}');
  t = t.replace(/[⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹]+/g, m => '^{' + [...m].map(c => ({ '⁻': '-', '⁺': '+', '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9' }[c])).join('') + '}');
  t = t.replace(/\^\([∗*]\)/g, '^{*}').replace(/\^\(\+\)/g, '^{+}');
  t = t.replace(/_\(([^)]+)\)/g, '_{$1}').replace(/\^\(([^)]+)\)/g, '^{$1}');
  t = t.replace(/([A-Za-z]|\\Sigma)\*/g, '$1^{*}');
  t = t.replace(/\\Sigma \*/g, '\\Sigma^{*}');

  if (cmdPlaceholders.length) t = t.replace(/\x02CMD(\d+)\x02/g, (_, i) => cmdPlaceholders[Number(i)]);
  return t.replace(/\s+/g, ' ').trim();
}

function _prepareFmt(s) {
  s = String(s);
  const mathBlocks = [];
  const pushMath = (tex, display = false) => {
    const idx = mathBlocks.length;
    mathBlocks.push({ tex, display });
    return `\x00MATH${idx}\x00`;
  };
  const subMath = (regex, mapFn = toLatexMathStr) => {
    s = s.replace(regex, m => {
      if (m.includes('\x00')) return m;
      const lead = (m.match(/^\s+/) || [''])[0];
      const trail = (m.match(/\s+$/) || [''])[0];
      const core = m.trim();
      if (!core) return m;
      return lead + pushMath(mapFn(core), false) + trail;
    });
  };
  const unwrapDen = d => {
    d = d.trim();
    while (d.startsWith('(') && d.endsWith(')')) {
      let depth = 0, coversAll = true;
      for (let i = 0; i < d.length - 1; i++) {
        if (d[i] === '(') depth++;
        else if (d[i] === ')') {
          depth--;
          if (depth === 0) { coversAll = false; break; }
        }
      }
      if (!coversAll || depth !== 1) break;
      d = d.slice(1, -1).trim();
    }
    return d;
  };
  const hasProseWord = t => /[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]/.test(t) || /\b(?!nad\b)[A-Za-z]{2,}\b/.test(t.replace(/_[A-Za-z0-9]+/g, ''));

  if (s.includes('$') || s.includes('\\(') || s.includes('\\[')) {
    s = s.replace(/\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$([^\$\n]+?)\$/g, (m, d1, d2, i1, i2) => {
      const isDisplay = d1 !== undefined || d2 !== undefined;
      const tex = (d1 !== undefined ? d1 : d2 !== undefined ? d2 : i1 !== undefined ? i1 : i2).trim();
      return pushMath(tex, isDisplay);
    });
  }

  // Automatický převod čistých i vložených matematických výrazů do LaTeX/KaTeX (jen pokud je načtený reálný KaTeX s .version)
  if (typeof katex !== 'undefined' && katex && katex.version && mathBlocks.length === 0) {
    const trimmed = s.trim();
    // 1. Čistý zlomek (např. "n! / ((n-k)! · k!)", "n! / (n-k)!")
    const fracMatch = trimmed.match(/^([0-9A-Za-z()−\-+·…!\s_]+)\s*\/\s*([0-9A-Za-z()−\-+·…!\s_]+)$/);
    if (fracMatch && !hasProseWord(trimmed) && (trimmed.includes('!') || trimmed.includes('−') || trimmed.includes('·') || /^\d+\s*\/\s*\d+$/.test(trimmed))) {
      return { wholeMath: { tex: `\\frac{${toLatexMathStr(unwrapDen(fracMatch[1]))}}{${toLatexMathStr(unwrapDen(fracMatch[2]))}}`, display: false } };
    }
    // 2. Čistá rovnice / výraz (např. "V_k(n) = n! / (n−k)!", "a = a_n·Z^n + ...", "(n+k−1 nad k)", "n^k")
    const eqFrac = trimmed.match(/^([A-Za-z0-9_()′'!]+)\s*=\s*([0-9A-Za-z()−\-+·…!\s_]+)\s*\/\s*([0-9A-Za-z()−\-+·…!\s_]+)$/);
    if (eqFrac && !hasProseWord(eqFrac[2] + ' ' + eqFrac[3])) {
      return { wholeMath: { tex: `${toLatexMathStr(eqFrac[1])} = \\frac{${toLatexMathStr(unwrapDen(eqFrac[2]))}}{${toLatexMathStr(unwrapDen(eqFrac[3]))}}`, display: false } };
    }
    if (/^(?:[A-Za-z0-9_()′'!]+|[Σ∑Π∏]_\([^)]+\)\^[A-Za-z0-9]+|\|\{-?\d+\}\|)\s*=\s*[0-9A-Za-z()_\^−\-+·….\s!{}\[\]]+$/.test(trimmed) && !hasProseWord(trimmed)) {
      return { wholeMath: { tex: toLatexMathStr(trimmed), display: false } };
    }
    if (/^\([A-Za-z0-9+\-−\s]+\s+nad\s+[A-Za-z0-9+\-−\s?]+\)$/.test(trimmed) || /^[A-Za-z0-9]\^[A-Za-z0-9]$/.test(trimmed)) {
      return { wholeMath: { tex: toLatexMathStr(trimmed), display: false } };
    }

    // 3. Inline kombinační čísla, sumy, součiny, odmocniny a zlomky
    subMath(/(?:C\([A-Za-z0-9+\-−,\s]+\)\s*=\s*)?\([A-Za-z0-9+\-−\s]+?\s+nad\s+[A-Za-z0-9+\-−\s?]+?\)/g);
    subMath(/[Σ∑Π∏]_\([^)]+\)\^(?:\([^)]+\)|[A-Za-z0-9]+)(?:\s*[a-zA-Z]_[A-Za-z0-9ᵢⱼₖₙ]+)?/g);
    subMath(/√\([^)]+\)|√[0-9]+/g);
    subMath(/(?:\([0-9A-Za-z()+\-−·…_!]+\)|[0-9A-Za-z()−\-+·…_]+!)\s*\/\s*(?:\(\([0-9A-Za-z()−\-+·…!_\sᵢⱼₖₙ,]+\)\)!?|\([0-9A-Za-z()−\-+·…!_\sᵢⱼₖₙ,]+\)!?|[0-9A-Za-z_]+!)/g, expr => {
      const m = expr.match(/^([\s\S]+?)\s*\/\s*([\s\S]+)$/);
      return m ? `\\frac{${toLatexMathStr(unwrapDen(m[1]))}}{${toLatexMathStr(unwrapDen(m[2]))}}` : toLatexMathStr(expr);
    });
    subMath(/(^|[\s(,])(−?\d+\/\d+)(?=$|[\s.,;)])/g, m => {
      const p = m.trim().split('/');
      const sign = p[0].startsWith('−') || p[0].startsWith('-') ? '-' : '';
      return `${sign}\\frac{${p[0].replace(/^[−-]/, '')}}{${p[1]}}`;
    });

    // 4. Faktoriály a kombinační volání C(...), V_k(n), C_k(n), P(n)
    subMath(/(?:\([A-Za-z0-9+\-−]+\)!|[0-9A-Za-z]+!)\s*=\s*[A-Za-z0-9()+\-−·…!\s]+?(?=[.,;:]|\s+\([A-Za-z0-9+\-−\s]*[≤≥<>][A-Za-z0-9+\-−\s]*\)|\s+[áčďéěíňóřšťúůýžA-Za-z]{2,}|$)/g);
    subMath(/\b[CVP][′']?(?:_\([^)]+\)|_[A-Za-z0-9]+)?\([^)]+\)(?:\s*[+=]\s*[CVP][′']?(?:_\([^)]+\)|_[A-Za-z0-9]+)?\([^)]+\))*/g);
    subMath(/\([A-Za-z][−\-][A-Za-z](?:[−\-]1)?\)!|\([A-Za-z]\+1\)!|\b[0-9nkv]!/g);

    // 5. Množinové definice tvaru Q = {...}, L(G) = {...}, Π = {...}, Pot({a, b}) = {...}, A/{∼}, |{-5}| = 5
    subMath(/\|\{-?\d+\}\|\s*=\s*\d+/g);
    subMath(/(?:Pot\([^)]+\)|[LP]\([A-Za-z0-9]+\)|[A-Z]\/(?:\{∼\}|∼)|[A-ZΣΠδ](?:_[A-Za-z0-9]+)?)\s*=\s*\{(?:[^{}\n]|\{[^{}\n]*\}){1,96}\}/g);
    subMath(/\b[A-Z]\/(?:\{∼\}|∼)/g);
    subMath(/\bn\([A-Za-z0-9+\-−]+\)…\([A-Za-z0-9+\-−]+\)/g);

    // 6. Řetězce a vztahy (nerovnosti, množinové a logické operátory, přepisy u ⇒* z) — závorky a složené závorky vcelku
    const atom = String.raw`(?:[A-Za-z0-9ᵢⱼₖₙ₀-₉⁻⁺⁰-⁹′'ℕℤℚℝℂ∅¬∀∃!ΣΠδγλφαβV^*+−\-_…|]+|𝓛|\([0-9A-Za-z,ᵢⱼₖₙ₀-₉⁻⁺⁰-⁹′'∗*+\-−\s∪∩;ΠΣ]+\)(?:\^\([^)]+\))?|\{(?:[^{}\n]|\{[^{}\n]*\}){1,64}\})+`;
    subMath(new RegExp(`${atom}(?:\\s*(?:∃!|[≤≥≠≈≡∩∪⊆⊂⊇⊃∈∉∧∨⇒⇔→←↔↦∼=])(?:\\^\\([∗*+]\\)|\\*?)(?:\\s*¬)?\\s*${atom})+`, 'g'));
    subMath(/(?:¬\s*)+[A-Za-z]\s*⇒\s*(?:¬\s*)+[A-Za-z]|∀\s*[A-Za-z]\s*∈\s*[A-Za-zℝℕℤ](?:\s*;\s*[^,.;\n]+)?|∃!?\s*[A-Za-z]\s*∈\s*[A-Za-zℝℕℤ](?:\s*;\s*[^,.;\n]+)?/g);

    // 7. Samostatné množiny {1, 2, 3}, negace ¬ x, operátorové zápisy (Π ∪ Σ)^(+), Σ′^(+), identifikátory s indexy/exponenty a symboly
    subMath(/\{(?:[^{}\n]*?(?:[,;→∈⊆⊂∼…]|-?\d)[^{}\n]*?|[A-Za-zε∅∼]|aa)\}/g);
    subMath(/\([A-Za-zΣΠ∪∩,\s]+\)\^\([^)]+\)|Σ′\^\([∗*+]\)|Σ′/g);
    subMath(/¬\s*[A-Za-z]\b|(?:\([^)\n]+\)|[A-Za-zΣΠφ]|𝓛)_\([^)]+\)(?:\^\([^)]+\))?|(?:[A-Za-zΣΠ]|𝓛)_[A-Za-z0-9]+|[A-Za-zΣΠ]\^\([^)]+\)|[A-Za-z]\^[A-Za-z0-9]+|\b[Vqpu][₀-₉]+\b|\bV\*(?!\w)|[ℕℤℚℝℂ∅∑∏∀∃¬∧∨⇒⇔→←↔↦]|(?<![A-Za-z])[ΣΠδεγλφ](?![A-Za-z])/g);
  }

  return { text: s, mathBlocks };
}

function fmtToFragment(s) {
  const frag = document.createDocumentFragment();
  const prep = _prepareFmt(s);
  if (prep.wholeMath) {
    frag.appendChild(renderLatexNode(prep.wholeMath.tex, prep.wholeMath.display));
    return frag;
  }
  const { text, mathBlocks } = prep;
  const tokRe = /\x00MATH(\d+)\x00|_\(([^)]+)\)|_([A-Za-z0-9]+)|\^\(([^)]+)\)|\^([A-Za-z0-9]+)|([₀-₉]+)|(->|<-|\.\.\.)/g;
  let pos = 0;
  for (const m of text.matchAll(tokRe)) {
    if (m.index > pos) frag.appendChild(document.createTextNode(text.slice(pos, m.index)));
    if (m[1] !== undefined) {
      const blk = mathBlocks[Number(m[1])];
      frag.appendChild(renderLatexNode(blk.tex, blk.display));
    } else if (m[2] !== undefined || m[3] !== undefined) {
      const subEl = document.createElement('sub');
      subEl.textContent = m[2] !== undefined ? m[2] : m[3];
      frag.appendChild(subEl);
    } else if (m[4] !== undefined || m[5] !== undefined) {
      const supEl = document.createElement('sup');
      supEl.textContent = m[4] !== undefined ? m[4] : m[5];
      frag.appendChild(supEl);
    } else if (m[6] !== undefined) {
      const subEl = document.createElement('sub');
      subEl.textContent = [...m[6]].map(c => '₀₁₂₃₄₅₆₇₈₉'.indexOf(c)).join('');
      frag.appendChild(subEl);
    } else if (m[7] !== undefined) {
      const map = { '->': '→', '<-': '←', '...': '…' };
      frag.appendChild(document.createTextNode(map[m[7]] || m[7]));
    }
    pos = m.index + m[0].length;
  }
  if (pos < text.length) frag.appendChild(document.createTextNode(text.slice(pos)));
  return frag;
}

function setFmt(targetEl, s) {
  if (!targetEl) return targetEl;
  targetEl.replaceChildren(fmtToFragment(s));
  return targetEl;
}


