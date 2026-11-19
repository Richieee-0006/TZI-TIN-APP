/* Bezpečná tvorba DOM/SVG uzlů bez innerHTML (kompatibilní s Trusted Types 'none'). */
(function (root) {
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const BLOCKED_PROPS = new Set(['innerHTML', 'outerHTML', 'insertAdjacentHTML']);

  function appendChildSafe(parent, item) {
    if (item === null || item === undefined || item === false) return;
    if (Array.isArray(item)) {
      for (const x of item) appendChildSafe(parent, x);
    } else if ((typeof Node !== 'undefined' && item instanceof Node) || (item && typeof item === 'object' && typeof item.nodeType === 'number')) {
      parent.appendChild(item);
    } else {
      parent.appendChild(document.createTextNode(String(item)));
    }
  }

  function applyProps(node, props, isSvg) {
    if (!props) return;
    for (const [k, v] of Object.entries(props)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'on' && typeof v === 'object') {
        for (const [ev, fn] of Object.entries(v)) {
          if (typeof fn === 'function') node.addEventListener(ev, fn);
        }
        continue;
      }
      if (BLOCKED_PROPS.has(k) || /^on/i.test(k)) {
        throw new Error(`Unsafe DOM prop rejected: ${k}`);
      }
      if (k === 'dataset' && typeof v === 'object') {
        for (const [dk, dv] of Object.entries(v)) {
          if (dv !== null && dv !== undefined && dv !== false) node.dataset[dk] = String(dv);
        }
      } else if (k === 'class' || k === 'className') {
        node.setAttribute('class', String(v));
      } else if (k === 'text') {
        node.textContent = String(v);
      } else if (!isSvg && (k === 'value' || k === 'checked' || k === 'disabled' || k === 'hidden' || k === 'selected' || k === 'open')) {
        node[k] = v;
      } else if (v === true) {
        node.setAttribute(k, '');
      } else {
        node.setAttribute(k, String(v));
      }
    }
  }

  function el(tag, props, ...children) {
    const node = document.createElement(tag);
    applyProps(node, props, false);
    appendChildSafe(node, children);
    return node;
  }

  function svgEl(tag, attrs, ...children) {
    const node = document.createElementNS(SVG_NS, tag);
    applyProps(node, attrs, true);
    appendChildSafe(node, children);
    return node;
  }

  function setChildren(parent, ...children) {
    const frag = document.createDocumentFragment();
    appendChildSafe(frag, children);
    parent.replaceChildren(frag);
    return parent;
  }

  function iconSvg(specs, cls = 'ico') {
    const nodes = specs.map(([tag, attrs]) => svgEl(tag, attrs));
    return svgEl('svg', { class: cls, viewBox: '0 0 24 24', 'aria-hidden': 'true' }, nodes);
  }

  root.TziDom = { el, svgEl, setChildren, iconSvg, appendChildSafe };
})(typeof window !== 'undefined' ? window : globalThis);
