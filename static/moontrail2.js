/* Moon Trail 2 — live OBS overlay. Reads real inputs from the local server's /events stream.
   URL options: ?demo=1 (loop a fake teamfight, for setting it up in OBS), ?heat=0, ?burst=0, ?kill=0 */
(() => {
"use strict";
const params = new URLSearchParams(location.search);
const T = {heat: params.get("heat") !== "0", burst: params.get("burst") !== "0", kill: params.get("kill") !== "0"};
const CFG = {slot:42, gap:6, pad:8, maxTiles:8, ttl:8000, heatWindow:2000, killWindow:3000, aaStack:2500};
const COLOR = {
  "weapon-calibrum":"#75e5ff", "weapon-severum":"#ff5969", "weapon-gravitum":"#b17dff",
  "weapon-infernum":"#529dff", "weapon-crescendum":"#f4dca3",
  "spell-w":"#78f1ff", "spell-r":"#ff4e64", "auto":"#edc26f",
};
const ICON = k => `/static/hud_small/${k}.png`;

const mt = document.getElementById("mt"), tilesEl = document.getElementById("tiles");
const now = () => performance.now();
let tiles = [];        // oldest first: {el, kind, count, t}
let castTimes = [];

function layout(){
  tiles.forEach((tl,i)=>{
    tl.el.style.left = (CFG.pad + i*(CFG.slot+CFG.gap)) + "px";
    tl.el.classList.toggle("dim", i < tiles.length-3);
  });
  const w = tiles.length ? CFG.pad*2 + tiles.length*CFG.slot + (tiles.length-1)*CFG.gap : 60;
  mt.style.setProperty("--rw", w+"px");
  mt.classList.toggle("visible", tiles.length>0);
}
function removeTile(tl){ tl.el.classList.add("leave"); setTimeout(()=>tl.el.remove(), 300); }

// item: {label, icon, kind} as sent by the server
function cast(item){
  const t = now();
  const kind = COLOR[item.kind] ? item.kind : "auto";
  const color = COLOR[kind];
  const label = item.label || "AA";
  const isAA = kind === "auto", isR = kind === "spell-r";
  const last = tiles[tiles.length-1];
  let el;
  if(isAA && last && last.kind==="auto" && t-last.t < CFG.aaStack){
    last.count++; last.t = t;
    const c = last.el.querySelector(".cnt");
    c.textContent = "×"+last.count; c.classList.add("show");
    c.classList.remove("bump"); void c.offsetWidth; c.classList.add("bump");
    el = last.el;
  } else {
    el = document.createElement("div");
    el.className = "tile enter "+kind;
    el.innerHTML = `<img alt="" draggable="false"><span class="key"></span><span class="cnt"></span>`;
    el.querySelector("img").src = item.icon;
    el.querySelector(".key").textContent = label;
    tilesEl.appendChild(el);
    tiles.push({el, kind, count:1, t});
    setTimeout(()=>el.classList.remove("enter"),650);
    while(tiles.length > CFG.maxTiles) removeTile(tiles.shift());
  }
  layout();
  requestAnimationFrame(()=>{ if(T.burst) burstAt(el, color, isR?46:isAA?10:24); });
  if(isR){ mt.classList.remove("sweep"); void mt.offsetWidth; mt.classList.add("sweep"); }
  castTimes.push(t); updateHeat(color);
}

function kill(){
  if(!T.kill) return;
  const t = now();
  const inv = tiles.filter(tl=>t-tl.t <= CFG.killWindow);
  if(!inv.length) return;
  inv.forEach(tl=>{ tl.el.classList.add("killed"); tl.t = t + 1500; });
  const tag = document.createElement("div");
  tag.className = "killtag"; tag.textContent = "KILL";
  tag.style.left = parseFloat(inv[0].el.style.left) + "px";
  mt.appendChild(tag);
  inv.forEach(tl=>burstAt(tl.el, "#ffd36b", 16));
  setTimeout(()=>{ tag.style.transition="opacity .3s"; tag.style.opacity="0"; setTimeout(()=>tag.remove(),320);
    inv.forEach(tl=>tl.el.classList.remove("killed")); }, 2200);
}

let heatColor = "#ff6a3d";
function updateHeat(color){
  const t = now();
  castTimes = castTimes.filter(x=>t-x<=CFG.heatWindow);
  const n = castTimes.length;
  const lvl = !T.heat ? 0 : n>=7 ? 3 : n>=5 ? 2 : n>=3 ? 1 : 0;
  if(color) heatColor = color;
  mt.style.setProperty("--hc", lvl>=3 ? "#ffd27a" : heatColor);
  mt.dataset.heat = lvl;
}
setInterval(()=>{
  const t = now(); let changed = false;
  while(tiles.length && t - tiles[0].t > CFG.ttl){ removeTile(tiles.shift()); changed = true; }
  if(changed) layout();
  updateHeat();
}, 250);

/* particles */
const cv = document.getElementById("fx"), ctx = cv.getContext("2d");
let parts = [], raf = null;
function sizeCanvas(){ cv.width = cv.offsetWidth*2; cv.height = cv.offsetHeight*2; }
sizeCanvas(); addEventListener("resize", sizeCanvas);
function burstAt(el, color, n){
  const c = cv.getBoundingClientRect(), r = el.getBoundingClientRect();
  if(!c.width) return;
  const sx = cv.width/c.width, sy = cv.height/c.height;
  const x = (r.left + r.width/2 - c.left)*sx, y = (r.top + r.height/2 - c.top)*sy;
  for(let i=0;i<n;i++){
    const a = Math.random()*Math.PI*2, s = (1.5+Math.random()*4.5)*(n>40?1.6:1);
    parts.push({x,y,vx:Math.cos(a)*s,vy:Math.sin(a)*s-1,life:1,dec:.022+Math.random()*.03,size:2+Math.random()*4,color,shard:Math.random()<.5,rot:a});
  }
  if(parts.length > 400) parts = parts.slice(-400);
  if(!raf) raf = requestAnimationFrame(tick);
}
function tick(){
  ctx.clearRect(0,0,cv.width,cv.height);
  parts = parts.filter(p=>p.life>0);
  for(const p of parts){
    p.x+=p.vx; p.y+=p.vy; p.vx*=.94; p.vy=p.vy*.94+.05; p.life-=p.dec;
    ctx.globalAlpha = Math.max(0,p.life); ctx.fillStyle = p.color; ctx.shadowColor = p.color; ctx.shadowBlur = 10;
    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot);
    if(p.shard){ ctx.beginPath(); ctx.moveTo(-p.size*1.6,0); ctx.lineTo(0,-p.size*.5); ctx.lineTo(p.size*1.6,0); ctx.lineTo(0,p.size*.5); ctx.fill(); }
    else { ctx.beginPath(); ctx.arc(0,0,p.size*.6,0,Math.PI*2); ctx.fill(); }
    ctx.restore();
  }
  ctx.globalAlpha = 1; ctx.shadowBlur = 0;
  raf = parts.length ? requestAnimationFrame(tick) : null;
}

/* demo mode: http://127.0.0.1:5002/hud?demo=1 */
if(params.get("demo") === "1"){
  const Q = w => ({label:"Q", icon:ICON("q_"+w), kind:"weapon-"+w});
  const W = {label:"W", icon:ICON("w"), kind:"spell-w"}, R = {label:"R", icon:ICON("r"), kind:"spell-r"}, A = {label:"AA", icon:ICON("aa"), kind:"auto"};
  const seq = [[50,Q("gravitum")],[300,A],[200,R],[200,A],[300,A],[250,W],[250,Q("infernum")],[150,A],[300,A],[250,"kill"],[1600,A],[500,A],[400,W],[300,Q("calibrum")]];
  const loop = () => { let t=0; seq.forEach(([ms,it])=>{ t+=ms; setTimeout(()=> it==="kill" ? kill() : cast(it), t); }); setTimeout(loop, t+9000); };
  setTimeout(loop, 400);
  return;
}

/* live mode */
let lastId = null, lastKills = null;
const source = new EventSource("/events");
source.onopen = () => { lastId = null; lastKills = null; };   // server restarted: re-baseline, don't replay
source.onmessage = e => {
  let d; try { d = JSON.parse(e.data); } catch { return; }
  const items = Array.isArray(d.items) ? d.items : [];
  const maxId = items.reduce((m,i)=>Math.max(m, Number(i.id)||0), 0);
  const kills = Number(d.kills)||0;
  if(lastId === null){ lastId = maxId; lastKills = kills; return; }
  items.filter(i=>Number(i.id) > lastId).sort((a,b)=>a.id-b.id).forEach(cast);
  if(maxId > lastId) lastId = maxId;
  if(kills > lastKills) kill();
  lastKills = kills;
};
addEventListener("pagehide", ()=>source.close(), {once:true});
})();
