() => {
  const numbers = color => color.match(/[\d.]+/g).map(Number);
  const luminance = color => numbers(color).slice(0,3).map(n=>n/255).map(n=>n<=0.04045?n/12.92:((n+0.055)/1.055)**2.4).reduce((sum,n,i)=>sum+n*[.2126,.7152,.0722][i],0);
  const ratio = (a,b) => (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
  const failures=[];
  let tested=0, minimum=21;
  for(const e of document.querySelectorAll('body *')) {
    if(!e.getClientRects().length || e.closest('[aria-hidden="true"], .skip-link') || ![...e.childNodes].some(n=>n.nodeType===3 && n.textContent.trim())) continue;
    const s=getComputedStyle(e), fg=luminance(s.color);
    let backgrounds=[], parent=e;
    while(parent) {
      const ps=getComputedStyle(parent);
      backgrounds.push(...(ps.backgroundImage.match(/rgb\([^)]*\)/g)||[]));
      if(ps.backgroundColor!=='rgba(0, 0, 0, 0)') {backgrounds.push(ps.backgroundColor);break;}
      parent=parent.parentElement;
    }
    if(!backgrounds.length) backgrounds=['rgb(255,255,255)'];
    const actual=Math.min(...backgrounds.map(bg=>ratio(fg,luminance(bg))));
    const required=parseFloat(s.fontSize)>=24 || parseFloat(s.fontSize)>=18.66 && parseInt(s.fontWeight)>=700 ? 3 : 4.5;
    tested++; minimum=Math.min(minimum,actual);
    if(actual<required) failures.push({element:e.className||e.tagName,ratio:Math.round(actual*100)/100,required});
  }
  return {tested,minimum:Math.round(minimum*100)/100,failures};
}
