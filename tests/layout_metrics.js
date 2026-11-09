() => {
  const rect = (element) => {
    const r = element.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom};
  };
  const visible = (element) => !!element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden';
  const label = (element) => element.id || element.className || element.tagName;
  const overlaps = (a, b) => Math.min(a.right, b.right) - Math.max(a.x, b.x) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y) > 1;
  const elements = [...document.querySelectorAll('body *')];
  const outside = elements.filter(visible).filter(e => {
    if (e.closest('.skip-link')) return false;
    const r = rect(e);
    return r.x < -1 || r.right > document.documentElement.clientWidth + 1;
  }).map(label);
  const clippedText = [];
  const obscuredText = [];
  for (const e of elements.filter(visible)) {
    if (e.closest('[aria-hidden="true"], .skip-link, .decor-orb, .brand-icon')) continue;
    for (const node of e.childNodes) {
      if (node.nodeType !== Node.TEXT_NODE || !node.textContent.trim()) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      for (const r of range.getClientRects()) {
        if (r.width < 1) continue;
        // Rotated illustration text uses transformed bounding boxes; check page bounds
        // and hit testing, but not axis-aligned parent containment within that artwork.
        if (!e.closest('.visual-panel')) {
          const parent = rect(e.closest('a, p, h1, h2, h3, .hero-proof, .service-card, .bottom-note') || e);
          if (r.left < parent.x - 2 || r.right > parent.right + 2) clippedText.push(label(e));
        }
        const x = (r.left + r.right) / 2, y = (r.top + r.bottom) / 2;
        if (x >= 0 && x < innerWidth && y >= 0 && y < innerHeight) {
          const top = document.elementFromPoint(x, y);
          if (top && top !== e && !e.contains(top) && !top.contains(e)) obscuredText.push(label(e));
        }
      }
    }
  }
  const blocks = Object.fromEntries(['.hero-content','.hero-visual','.hero-actions','.site-header','.nav','.header-cta','.brand','.partners','.services'].map(s=>[s,rect(document.querySelector(s))]));
  const actions = [...document.querySelectorAll('.hero-actions a')].map(rect);
  const cards = [...document.querySelectorAll('.service-card')].map(rect);
  const links = [...document.querySelectorAll('a')].filter(e=>!e.classList.contains('skip-link')).map(e=>({text:e.textContent.trim(),href:e.getAttribute('href'),visible:visible(e),...rect(e)}));
  const invalidLinks = links.filter(e=>!e.href.startsWith('#') && e.href !== './index.html' || e.href.startsWith('#') && !document.getElementById(e.href.slice(1))).map(e=>e.href);
  const pairs = [['.brand','.nav'],['.nav','.header-cta'],['.brand','.header-cta'],['.hero-content','.hero-visual']];
  const collisions = pairs.filter(([a,b])=>overlaps(blocks[a],blocks[b])).map(p=>p.join(' / '));
  if (overlaps(actions[0], actions[1])) collisions.push('hero actions');
  for (let i=0;i<cards.length;i++) for(let j=i+1;j<cards.length;j++) if(overlaps(cards[i],cards[j])) collisions.push(`cards ${i}/${j}`);
  return {
    clientWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,
    broken:document.documentElement.classList.contains('broken'),
    shellOverflow:getComputedStyle(document.querySelector('.site-shell')).overflowX,
    outside,clippedText:[...new Set(clippedText)],obscuredText:[...new Set(obscuredText)],
    blocks,cards,links,invalidLinks,collisions,
    navVisible:visible(document.querySelector('.nav')),
    images:[...document.images].map(e=>({loaded:e.complete && e.naturalWidth>0,...rect(e)})),
    headingCount:document.querySelectorAll('h1').length,
    hasViewport:!!document.querySelector('meta[name="viewport"]'),
    hasLang:!!document.documentElement.lang
  };
}
