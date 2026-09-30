// Fictional demo only. Exercises real chart controls and sampled visual conditions.
import type { BrowserWindow, WebFrameMain } from "electron";
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { delay } from "./proc";

type LayoutResult = { reflow: boolean; targets: boolean; unclippedControls: boolean };
type ContrastResult = { count: number; min: number; failures: unknown[] };

const spacing = `* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-bottom: 2em !important; }`;
const textResizeRules = `(() => [...document.querySelectorAll('body *')].filter(el => !el.closest('script,style,svg')).map((el,i) => {
  el.setAttribute('data-text-resize',i); return '[data-text-resize="'+i+'"] { font-size: '+parseFloat(getComputedStyle(el).fontSize)*2+'px !important; }';
}).join('\\n'))()`;
const layoutProbe = `(() => {
  const visible = el => !!el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const controls = [...document.querySelectorAll('button,input:not([type=hidden]),select,textarea,summary')].filter(visible);
  const tiny = controls.filter(el => el.tagName === 'BUTTON' && !el.disabled && (el.getBoundingClientRect().height < 24 || el.getBoundingClientRect().width < 24));
  const clipped = controls.filter(el => {
    if (el.closest('.table-scroll,table,.testlist,.results')) return false;
    const r = el.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth + 1;
  });
  const overflow = [...document.body.querySelectorAll("*")].filter(visible).filter(el => !el.closest(".table-scroll,table,.testlist,.results")).map(el => {
    const rect = el.getBoundingClientRect();
    return { element: el.id || el.className || el.tagName, right: rect.right, width: rect.width };
  }).filter(rect => rect.right > innerWidth + 1);
  return { reflow: document.documentElement.scrollWidth <= innerWidth + 1,
    targets: tiny.length === 0, unclippedControls: clipped.length === 0,
    width: innerWidth, scrollWidth: document.documentElement.scrollWidth, overflow,
    tiny: tiny.map(el => el.id || el.className), clipped: clipped.map(el => el.id || el.className) };
})()`;

// Composite rendered backgrounds rather than comparing token names alone.
const contrastProbe = `(() => {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d', {willReadFrequently:true});
  const rgba = color => { ctx.clearRect(0,0,1,1); ctx.fillStyle = color; ctx.fillRect(0,0,1,1); return [...ctx.getImageData(0,0,1,1).data].map((v,i) => i === 3 ? v / 255 : v); };
  const blend = (top,bottom) => [0,1,2].map(i => top[i]*top[3]+bottom[i]*(1-top[3])).concat(1);
  const background = el => { const parents = []; for (let p=el;p;p=p.parentElement) parents.unshift(p); return parents.reduce((bg,p) => blend(rgba(getComputedStyle(p).backgroundColor),bg),[255,255,255,1]); };
  const luminance = rgb => rgb.slice(0,3).map(v => { v/=255; return v<=.04045 ? v/12.92 : ((v+.055)/1.055)**2.4; }).reduce((s,v,i) => s+v*[.2126,.7152,.0722][i],0);
  const ratio = (a,b) => { const x=luminance(a),y=luminance(b); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); };
  const failures = []; let count=0,min=99;
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('svg,script,style,.sr-only') || !el.getClientRects().length || el.disabled || el.closest('[disabled]')) continue;
    if (![...el.childNodes].some(n => n.nodeType===3 && n.textContent.trim()) && !el.matches('input,textarea,select')) continue;
    const style=getComputedStyle(el); if (style.visibility==='hidden' || Number(style.opacity)===0) continue;
    const bg=background(el), fg=blend(rgba(style.color),bg), value=ratio(fg,bg);
    const large=parseFloat(style.fontSize)>=24 || (parseFloat(style.fontSize)>=18.66 && Number(style.fontWeight)>=700);
    count++;min=Math.min(min,value);
    if(value < (large?3:4.5)) failures.push({element:el.id || el.className || el.tagName,ratio:+value.toFixed(2)});
  }
  const borders=[];
  for(const el of document.querySelectorAll('input:not([type=checkbox]),textarea,select,.chip,.chart-controls button,.seg,button.ghost')) {
    if(!el.getClientRects().length || el.disabled) continue;
    const style=getComputedStyle(el),color=rgba(style.borderTopColor);
    if(style.borderTopStyle==='none' || color[3]===0) continue;
    const value=ratio(blend(color,background(el)),background(el));
    if(value<3) borders.push({element:el.id || el.className,ratio:+value.toFixed(2)});
  }
  failures.push(...borders);
  return {count,min:+min.toFixed(2),failures:failures.slice(0,15)};
})()`;

export async function runAccessibilitySmoke(window: BrowserWindow, frame: WebFrameMain, outDir: string): Promise<void> {
  const controls = await frame.executeJavaScript(`(async () => {
    const checks = {}, tick = () => new Promise(resolve => setTimeout(resolve,100));
    const submit = async (form,range) => {
      form.querySelectorAll('input')[0].value=range[0]; form.querySelectorAll('input')[1].value=range[1];
      form.querySelectorAll('input').forEach(el=>el.dispatchEvent(new Event('input')));
      form.requestSubmit(); await tick();
    };
    showTab('vitals'); await tick();
    const group=document.querySelector('.diabetes-dashboard'), form=group.querySelector('form');
    const charts=[...group.querySelectorAll('.js-plotly-plot')];
    const dates=DATA.vitals.filter(r=>r.metric==='CGM / meter glucose').map(r=>r.date).sort();
    const range=[dates.at(-14),dates.at(-1)]; await submit(form,range);
    checks.applyBoth=charts.every(c=>c.layout.xaxis.range[0]===range[0] && c.layout.xaxis.range[1]===range[1]);
    const before=Date.parse(charts[0].layout.xaxis.range[0]);
    [...form.querySelectorAll('button')].find(b=>b.textContent==='Previous window').click();await tick();
    checks.previousBoth=Date.parse(charts[0].layout.xaxis.range[0])<before && JSON.stringify(charts[0].layout.xaxis.range)===JSON.stringify(charts[1].layout.xaxis.range);
    [...form.querySelectorAll('button')].find(b=>b.textContent==='Next window').click();await tick();
    checks.nextBoth=Date.parse(charts[0].layout.xaxis.range[0])===before;
    showTab('records');showTab('vitals');checks.tabRange=Date.parse(charts[0].layout.xaxis.range[0])===before;
    const old=[...charts[0].layout.xaxis.range]; await submit(form,[range[1],range[0]]);
    checks.invalidRange=JSON.stringify(old)===JSON.stringify(charts[0].layout.xaxis.range);
    [...form.querySelectorAll('button')].find(b=>b.textContent==='Reset view').click();await tick();
    checks.resetBoth=Date.parse(charts[0].layout.xaxis.range[0])<before && JSON.stringify(charts[0].layout.xaxis.range)===JSON.stringify(charts[1].layout.xaxis.range);
    checks.averageEquivalent=[...group.querySelectorAll('th')].some(el=>el.textContent==='30-day average');
    showLabsFor(TOPICS[0].name);await tick();
    for(let i=0;i<30 && !document.querySelector('#labcharts .js-plotly-plot');i++) await tick();
    const lab=document.querySelector('#labcharts .js-plotly-plot');
    if(!lab) throw new Error('The selected topic lab chart did not finish rendering');
    const card=lab.closest('.card');
    const labDates=lab.data[0].x.map(d=>d.slice(0,10)).sort();
    await submit(card.querySelector('form'),[labDates[0],labDates.at(-1)]);
    checks.labApply=lab.layout.xaxis.range[0]===labDates[0];
    checks.labDetails=card.querySelector('table').textContent.includes('Order / comments');
    Plotly.Fx.hover(lab,[{curveNumber:0,pointNumber:0}]);await tick();
    const tooltip=lab.querySelector('.hovertext');
    checks.hoverable=!!tooltip && getComputedStyle(tooltip).pointerEvents==='all';
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));await tick();
    checks.dismissHover=!lab.querySelector('.hovertext') && lab.hoverDismissed===true;
    checks.markerDetails=[...card.querySelectorAll('summary')].some(el=>el.textContent==='Marked events');
    const pts=labState.byTest.get(lab.dataset.test);
    checks.sourceEquivalence=pts.every(p=>(!p.cm || card.textContent.includes(p.cm)) && (!p.on || card.textContent.includes(p.on)));
    showTab('overview');await tick();
    const timeline=document.getElementById('timeline'), timelineForm=document.getElementById('timeline-controls');
    await submit(timelineForm,['2025-01-01','2025-03-01']);
    checks.timelineApply=timeline.layout.xaxis.range[0]==='2025-01-01';
    checks.timelineStatus=timelineForm.querySelector('[role=status]').textContent.includes('2025');
    return checks;
  })()`) as Record<string, boolean>;
  if (!Object.values(controls).every(Boolean)) throw new Error(`Chart controls: ${JSON.stringify(controls)}`);
  process.stdout.write(`Accessible chart controls passed ${Object.keys(controls).length} checks.\n`);

  const evidence: unknown[] = [];
  const save = async (name: string) => writeFileSync(join(outDir,name+'.png'),(await window.webContents.capturePage()).toPNG(),{flag:'wx',mode:0o600});
  await frame.executeJavaScript('showTab("vitals");document.querySelector(".diabetes-dashboard").scrollIntoView({block:"start"})');
  await delay(150); await save('accessibility-chart-controls');
  for (const factor of [2,4]) {
    window.webContents.setZoomFactor(factor);
    await delay(200);
    for (const tab of ['import','build','events','notes','doctor','dashboard']) {
      window.webContents.send('tab',tab);await delay(200);
      const shell = await window.webContents.executeJavaScript(layoutProbe);
      evidence.push({zoom:factor,tab,shell});
      if (!shell.reflow || !shell.targets || !shell.unclippedControls) throw new Error(`Shell zoom ${factor} ${tab}: ${JSON.stringify(shell)}`);
      if(tab==='dashboard') {
        for (const view of ['overview','labs','vitals','records']) {
          await frame.executeJavaScript('showTab('+JSON.stringify(view)+')');await delay(150);
          const result = await frame.executeJavaScript(layoutProbe) as LayoutResult;
          evidence.push({zoom:factor,view,result});
          if(!result.reflow || !result.targets || !result.unclippedControls) throw new Error(`Dashboard zoom ${factor} ${view}: ${JSON.stringify(result)}`);
        }
      }
    }
    await save(`accessibility-zoom-${factor}`);
  }
  window.webContents.setZoomFactor(1);await delay(150);
  for(const tab of ['import','build','events','notes','doctor','dashboard']) {
    window.webContents.send('tab',tab);await delay(150);
    const rules=await window.webContents.executeJavaScript(textResizeRules);
    const css=await window.webContents.insertCSS(rules);
    const result=await window.webContents.executeJavaScript(layoutProbe);evidence.push({textResize:2,tab,result});
    await save("accessibility-text-200-shell-"+tab);
    await window.webContents.removeInsertedCSS(css);
    if(!result.reflow || !result.unclippedControls) throw new Error(`Shell 200% text ${tab}: ${JSON.stringify(result)}`);
  }
  for(const view of ['overview','labs','vitals','records']) {
    await frame.executeJavaScript('showTab('+JSON.stringify(view)+')');await delay(150);
    const rules=await frame.executeJavaScript(textResizeRules);
    await frame.executeJavaScript('var resizeStyle=document.createElement("style");resizeStyle.textContent='+JSON.stringify(rules)+';document.head.append(resizeStyle)');
    const result=await frame.executeJavaScript(layoutProbe) as LayoutResult;evidence.push({textResize:2,view,result});
    await save('accessibility-text-200-'+view);
    await frame.executeJavaScript('resizeStyle.remove()');
    if(!result.reflow || !result.unclippedControls) throw new Error(`Dashboard 200% text ${view}: ${JSON.stringify(result)}`);
  }
  const shellSpacing=await window.webContents.insertCSS(spacing);
  await frame.executeJavaScript('var spacingStyle=document.createElement("style");spacingStyle.textContent='+JSON.stringify(spacing)+';document.head.append(spacingStyle)');
  for(const tab of ['import','build','events','notes','doctor','dashboard']) {
    window.webContents.send('tab',tab);await delay(150);
    const result=await window.webContents.executeJavaScript(layoutProbe);evidence.push({spacing:true,tab,result});
    if(!result.reflow || !result.unclippedControls) throw new Error(`Shell text spacing ${tab}: ${JSON.stringify(result)}`);
  }
  for(const view of ['overview','labs','vitals','records']) {
    await frame.executeJavaScript('showTab('+JSON.stringify(view)+')');await delay(150);
    const result=await frame.executeJavaScript(layoutProbe) as LayoutResult;evidence.push({spacing:true,view,result});
    if(!result.reflow || !result.unclippedControls) throw new Error(`Dashboard text spacing ${view}: ${JSON.stringify(result)}`);
  }
  await save('accessibility-text-spacing');
  await window.webContents.removeInsertedCSS(shellSpacing);await frame.executeJavaScript('spacingStyle.remove()');
  process.stdout.write("Zoom, 200% text, and spacing samples passed; checking long labels and focus.\n");
  await window.webContents.executeJavaScript('document.getElementById("dashboard").style.width="320px"');
  const longTopic=await frame.executeJavaScript(`(() => {
    const original=TOPICS[0].name;TOPICS[0].name='FictionalLongTopic'.repeat(12);showRecordsFor(TOPICS[0].name);return original;
  })()`);
  const longResult=await frame.executeJavaScript(layoutProbe) as LayoutResult;
  evidence.push({longTopic:longResult});
  if(!longResult.reflow || !longResult.unclippedControls) throw new Error('Long topic reflow: '+JSON.stringify(longResult));
  await frame.executeJavaScript('TOPICS[0].name='+JSON.stringify(longTopic)+';showRecordsFor(TOPICS[0].name)');
  await window.webContents.executeJavaScript('document.getElementById("dashboard").style.width=""');
  window.webContents.send('tab','import');window.webContents.setZoomFactor(4);await delay(150);
  await window.webContents.executeJavaScript(`(() => {
    const fixture=document.createElement('div');fixture.id='long-source-fixture';fixture.className='source-row';
    fixture.innerHTML='<div><span>'+('FictionalLongSource'.repeat(12))+'</span></div><span>Fictional source metadata</span>';
    document.getElementById('current-sources').append(fixture);
  })()`);

  const longSource=await window.webContents.executeJavaScript(layoutProbe);evidence.push({longSource});
  if(!longSource.reflow || !longSource.unclippedControls) throw new Error('Long source reflow: '+JSON.stringify(longSource));
  await window.webContents.executeJavaScript('document.getElementById("long-source-fixture").remove();document.querySelector("#tabs [aria-selected=true]").focus()');
  window.focus(); window.webContents.focus();
  window.webContents.sendInputEvent({type:'keyDown',keyCode:'Tab'});window.webContents.sendInputEvent({type:'keyUp',keyCode:'Tab'});await delay(150);
  const focus=await window.webContents.executeJavaScript(`(() => {
    const el=document.activeElement,r=el.getBoundingClientRect(),style=getComputedStyle(el);
    const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
    return {visible:style.outlineStyle!=='none' && parseFloat(style.outlineWidth)>=2,
      unobscured:el===hit || el.contains(hit),inViewport:r.top>=0 && r.bottom<=innerHeight};
  })()`);
  evidence.push({keyboardFocusAt400:focus});
  if(!Object.values(focus).every(Boolean)) throw new Error('400% keyboard focus: '+JSON.stringify(focus));
  await save('accessibility-focus-400');window.webContents.setZoomFactor(1);
  process.stdout.write("Long labels and 400% focus passed; measuring rendered contrast.\n");
  for(const theme of ['light','dark','system']) {
    await window.webContents.executeJavaScript('document.querySelector(\'[data-theme-value="'+theme+'"]\').click()');await delay(200);
    for(const tab of ['import','build','events','notes','doctor','dashboard']) {
      window.webContents.send('tab',tab);await delay(150);
      const result=await window.webContents.executeJavaScript(contrastProbe);evidence.push({theme,tab,contrast:result});
      if(result.failures.length) throw new Error(`Shell contrast ${theme} ${tab}: ${JSON.stringify(result)}`);
    }
    for(const view of ['overview','labs','vitals','records']) {
      await frame.executeJavaScript('showTab('+JSON.stringify(view)+')');await delay(150);
      const result=await frame.executeJavaScript(contrastProbe) as ContrastResult;evidence.push({theme,view,contrast:result});
      if(result.failures.length) throw new Error(`Dashboard contrast ${theme} ${view}: ${JSON.stringify(result)}`);
    }
  }
  const forced = await window.webContents.executeJavaScript('matchMedia("(forced-colors: active)").matches');
  evidence.push({forcedColorsActive:forced});
  writeFileSync(join(outDir,'accessibility-evidence.json'),JSON.stringify({controls,evidence},null,2),{flag:'wx',mode:0o600});
  process.stdout.write(`Visual accessibility passed ${evidence.length-1} sampled conditions; forced colors active: ${forced}.\n`);
}
