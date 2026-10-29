function renderLatexExpr(tex, displayMode) {
  if (typeof katex !== 'undefined' && katex && typeof katex.renderToString === 'function') {
    try {
      return katex.renderToString(tex, { displayMode: !!displayMode, throwOnError: false });
    } catch (e) {}
  }
  return `<span class="math-tex katex-fallback" data-display="${displayMode ? '1' : '0'}">${esc(tex)}</span>`;
}

// Zápis z banky (LaTeX $...$, $$...$$, \(...\), \[...\] + a_n, Z^n, a_(n-1), ->) převede na HTML s KaTeXem a indexy.
function toLatexMathStr(raw) {
  let t = String(raw || '').trim();
  t = t.replace(/\(([A-Za-z0-9+\-−\s]+?)\s+nad\s+([A-Za-z0-9+\-−\s?]+?)\)/g, '\\binom{$1}{$2}');
  t = t.replace(/−/g, '-').replace(/·/g, ' \\cdot ').replace(/…|\.{3}/g, ' \\dots ');
  t = t.replace(/≤/g, ' \\le ').replace(/≥/g, ' \\ge ').replace(/≠/g, ' \\ne ');
  t = t.replace(/⊆/g, ' \\subseteq ').replace(/⊂/g, ' \\subset ').replace(/⊇/g, ' \\supseteq ');
  t = t.replace(/∩/g, ' \\cap ').replace(/∪/g, ' \\cup ').replace(/∈/g, ' \\in ').replace(/∉/g, ' \\notin ').replace(/∅/g, ' \\emptyset ');
  t = t.replace(/∧/g, ' \\land ').replace(/∨/g, ' \\lor ').replace(/¬/g, ' \\neg ').replace(/⇒/g, ' \\Rightarrow ').replace(/⇔/g, ' \\Leftrightarrow ').replace(/→/g, ' \\to ').replace(/∼/g, ' \\sim ');
  t = t.replace(/∀/g, ' \\forall ').replace(/∃/g, ' \\exists ');
  t = t.replace(/ᵢ/g, '_i').replace(/ⱼ/g, '_j').replace(/ₖ/g, '_k').replace(/ₙ/g, '_n').replace(/′/g, "'");
  t = t.replace(/[₀-₉]+/g, m => '_{' + [...m].map(c => '₀₁₂₃₄₅₆₇₈₉'.indexOf(c)).join('') + '}');
  t = t.replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]+/g, m => '^{' + [...m].map(c => '⁰¹²³⁴⁵⁶⁷⁸⁹'.indexOf(c)).join('') + '}');
  t = t.replace(/_\(([^)]+)\)/g, '_{$1}').replace(/\^\(([^)]+)\)/g, '^{$1}');
  return t;
}

function fmt(s) {
  s = String(s);
  const mathBlocks = [];
  const pushMath = (tex, display = false) => {
    const idx = mathBlocks.length;
    mathBlocks.push(renderLatexExpr(tex, display));
    return `\x00MATH${idx}\x00`;
  };

  if (s.includes('$') || s.includes('\\(') || s.includes('\\[')) {
    s = s.replace(/\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$([^\$\n]+?)\$/g, (m, d1, d2, i1, i2) => {
      const isDisplay = d1 !== undefined || d2 !== undefined;
      const tex = (d1 !== undefined ? d1 : d2 !== undefined ? d2 : i1 !== undefined ? i1 : i2).trim();
      return pushMath(tex, isDisplay);
    });
  }

  // Automatic LaTeX/KaTeX conversion for plain-text math in banks when real KaTeX is loaded
  if (typeof katex !== 'undefined' && katex && katex.version && mathBlocks.length === 0) {
    const trimmed = s.trim();
    // 1. Pure fraction option/expression (e.g. "n! / ((n-k)! · k!)", "(n-k)! · k! / n!", "n·(n-1)·…·(n-k+1) / k!")
    const fracMatch = trimmed.match(/^([0-9A-Za-z()−\-+·…!\s_]+)\s*\/\s*([0-9A-Za-z()−\-+·…!\s_]+)$/);
    if (fracMatch && (trimmed.includes('!') || trimmed.includes('−') || trimmed.includes('·'))) {
      let num = fracMatch[1].trim();
      let den = fracMatch[2].trim();
      if (den.startsWith('((') && den.endsWith('))')) den = den.slice(1, -1);
      else if (den.startsWith('(') && den.endsWith(')') && !den.slice(1, -1).includes('(')) den = den.slice(1, -1);
      return renderLatexExpr(`\\frac{${toLatexMathStr(num)}}{${toLatexMathStr(den)}}`, false);
    }
    // 2. Pure equation option (e.g. "n! = n·(n−1)·…·(n−k+1)·(n−k)!", "a = a_n·Z^n + a_(n-1)·Z^(n-1) + ... + a_1·Z^1 + a_0·Z^0")
    if (/^(?:n!|\(n[−\-]k\)!|\(k\+1\)!|a)\s*=\s*[0-9A-Za-z()_\^−\-+·….\s!]+$/.test(trimmed)) {
      return renderLatexExpr(toLatexMathStr(trimmed), false);
    }
    // 3. Inline C(n, k) = (n nad k) or (a nad b)
    s = s.replace(/(?:C\([A-Za-z0-9+\-−,\s]+\)\s*=\s*)?\(([A-Za-z0-9+\-−\s]+?)\s+nad\s+([A-Za-z0-9+\-−\s?]+?)\)/g, m => pushMath(toLatexMathStr(m), false));
    // 4. Inline fractions with factorials
    s = s.replace(/([0-9A-Za-z()−\-+·…]+!)\s*\/\s*(\(\([0-9A-Za-z()−\-+·!\s]+\)\)|\([0-9A-Za-z−\-+·!\s]+\)!?|[0-9A-Za-z]+!)/g, (_, num, den) => {
      let d = den.trim();
      if (d.startsWith('((') && d.endsWith('))')) d = d.slice(1, -1);
      return renderLatexExpr(`\\frac{${toLatexMathStr(num)}}{${toLatexMathStr(d)}}`, false);
    });
    // 5. Inline factorial equations & combinatorial expressions C(...), V(...), P(...)
    s = s.replace(/\([A-Za-z0-9+\-−]+\)!\s*=\s*[A-Za-z0-9()+\-−·…!\s]+/g, m => pushMath(toLatexMathStr(m), false));
    s = s.replace(/C'\([^)]+\)|C\([^)]+\)(?:\s*[+=]\s*C\([^)]+\))*/g, m => pushMath(toLatexMathStr(m), false));
    s = s.replace(/\([A-Za-z][−\-][A-Za-z](?:[−\-]1)?\)!|\([A-Za-z]\+1\)!|\b[0-9nkv]!\b/g, m => pushMath(toLatexMathStr(m), false));
    // 6. Inequalities & symbolic relations (0 ≤ k ≤ n, k+1 ≤ n, k ≤ n, k < n, i ≠ j, Aᵢ ∩ Aⱼ = ∅, X ⊆ Y, x ∧ y, x ⇒ y, etc.)
    s = s.replace(/[0-9A-Za-zᵢⱼ′'+\-−_()]+\s*(?:[≤≥≠∩∪⊆∈∉∧∨⇒⇔∼]\s*[0-9A-Za-zᵢⱼ′'∅¬+\-−_()]+\s*)+/g, m => pushMath(toLatexMathStr(m), false));
    s = s.replace(/¬[A-Za-z]\s*⇒\s*¬[A-Za-z]|∀[A-Za-z]\s*∈\s*[A-Za-z];\s*[A-Za-z0-9]+/g, m => pushMath(toLatexMathStr(m), false));
  }

  s = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  s = s
    .replace(/_\(([^)]+)\)/g, '<sub>$1</sub>').replace(/_([A-Za-z0-9]+)/g, '<sub>$1</sub>')
    .replace(/\^\(([^)]+)\)/g, '<sup>$1</sup>').replace(/\^([A-Za-z0-9]+)/g, '<sup>$1</sup>')
    .replace(/[₀-₉]+/g, m => '<sub>' + [...m].map(c => '₀₁₂₃₄₅₆₇₈₉'.indexOf(c)).join('') + '</sub>')
    .replace(/-&gt;/g, '→').replace(/&lt;-/g, '←').replace(/\.\.\./g, '…');
  if (mathBlocks.length > 0) {
    s = s.replace(/\x00MATH(\d+)\x00/g, (_, i) => mathBlocks[Number(i)]);
  }
  return s;
}


