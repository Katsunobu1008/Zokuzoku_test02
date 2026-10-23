const $ = id => document.getElementById(id);
const state = { ideas: [], map: new Map(), user: localStorage.getItem('zoku-user') || 'a', seq: 0, tab: 'explore', selected: null, shown: 12, search: '', sort: 'recent', camera: {x:0,y:0,s:1}, pointer: null, anim: null, frame: 0 };
const palette = ['#70cafa','#c494fa','#8fd8dc','#ffb2cc','#f5c27d','#7499ee'];
const escapeHTML = v => String(v ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
const short = (s, n=65) => String(s).length>n ? String(s).slice(0,n)+'…' : String(s);
const encode = encodeURIComponent;
function toast(message) { const n = $('toast'); n.textContent = message; n.classList.add('show'); clearTimeout(toast.timer); toast.timer = setTimeout(()=>n.classList.remove('show'),3400) }
async function api(path, options={}) {
  const response = await fetch(path,{...options,headers:{'X-Demo-User':state.user,...options.body?{'Content-Type':'application/json'}:{},...(options.headers||{})}});
  const result = await response.json().catch(()=>({error:'サーバーの応答を読み取れませんでした'}));
  if(!response.ok) throw new Error(result.error || 'HTTP '+response.status);
  return result;
}
function art(seed=0) { // Deterministic concept illustration; NOT AI-generated.
  const n = typeof seed === 'string' ? [...seed].reduce((a,c)=>a+c.charCodeAt(0),0) : seed;
  const color=palette[n%palette.length], second=palette[(n+2)%palette.length], angle=n%7;
  const fin = Array.from({length:6},(_,i)=>{const x=139+i*20;return `<path d="M ${x} 215 Q ${x-22+(i%3)*20} ${252+(i%4)*9} ${x+Math.sin(n+i)*32} ${285+(i%2)*16}" stroke="${i%2?second:color}" stroke-width="${12+(i%3)*3}" stroke-linecap="round" opacity=".75" fill="none"/>`}).join('');
  const bubbles=Array.from({length:13},(_,i)=>{const x=(i*49+n*17)%345+22,y=(i*67+n*11)%290+24;return `<circle cx="${x}" cy="${y}" r="${i%3+2}" fill="#fff" opacity=".58"/>`}).join('');
  return `<svg viewBox="0 0 400 360" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="クラゲのコンセプトアート"><defs><radialGradient id="bg${n}"><stop stop-color="#fff"/><stop offset="1" stop-color="${color}" stop-opacity=".45"/></radialGradient><radialGradient id="j${n}" cx=".3" cy=".18"><stop stop-color="#fff"/><stop offset=".48" stop-color="${color}"/><stop offset="1" stop-color="${second}"/></radialGradient><filter id="f${n}"><feGaussianBlur stdDeviation="11"/></filter></defs><rect width="400" height="360" fill="url(#bg${n})"/><circle cx="220" cy="168" r="130" fill="${color}" opacity=".21" filter="url(#f${n})"/>${bubbles}<g transform="translate(${angle-3} 0) rotate(${(angle-3)*2} 200 200)">${fin}<path d="M 102 198 C 102 86,300 86,300 198 Q 288 239 264 211 Q 244 235 224 213 Q 203 240 184 214 Q 163 238 145 210 Q 120 235 102 198 Z" fill="url(#j${n})" stroke="#ffffffb7" stroke-width="5"/><ellipse cx="160" cy="183" rx="7" ry="10" fill="#194d80"/><ellipse cx="243" cy="183" rx="7" ry="10" fill="#194d80"/><path d="M 188 194 Q 200 207 215 194" stroke="#1d527d" stroke-width="4" fill="none" stroke-linecap="round"/><ellipse cx="132" cy="205" rx="15" ry="7" fill="#ffb9d1" opacity=".52"/><ellipse cx="271" cy="205" rx="15" ry="7" fill="#ffb9d1" opacity=".52"/><ellipse cx="156" cy="134" rx="34" ry="16" transform="rotate(-34 156 134)" fill="#fff" opacity=".58"/></g></svg>`;
}
function artFor(idea) { return idea.image_path ? `<img alt="${escapeHTML(idea.title)}のAI商品画像" src="${escapeHTML(idea.image_path)}" loading="lazy">` : art([...idea.id].reduce((a,c)=>a+c.charCodeAt(0),0)); }
function parentName(idea) { return idea.parent_id && state.map.get(idea.parent_id)?.title || '独立したアイデア'; }
async function refresh(showNotice=false) {
  const data=await api('/api/ideas'); state.ideas=data.ideas; state.map=new Map(data.ideas.map(i=>[i.id,i]));state.seq=data.seq;
  $('totalIdeas').textContent=data.ideas.length; $('totalBranches').textContent=data.ideas.filter(x=>x.parent_id).length;
  if(showNotice) $('syncedLabel').textContent='新しい進化を反映';
  renderGrid(); if(state.selected) {const idea=state.map.get(state.selected);if(idea)renderDetail(idea,false)}
}
function getFiltered() {
  let xs=state.ideas.filter(i=>(i.title+' '+i.category+' '+i.mood+' '+i.prompt).includes(state.search));
  if(state.sort==='recent')xs.sort((a,b)=>b.created_at-a.created_at);
  else if(state.sort==='popular')xs.sort((a,b)=>(b.likes*3+b.support_points)-(a.likes*3+a.support_points));
  else xs.sort((a,b)=>String(a.id).localeCompare(String(b.id))*(Math.random()>.5?1:-1));
  return xs;
}
function renderGrid() {
  const data=getFiltered(), shown=data.slice(0,state.shown);
  $('ideaGrid').innerHTML=shown.map(x=>`<article class="idea-card" tabindex="0" data-open="${escapeHTML(x.id)}" role="button" aria-label="${escapeHTML(x.title)}を開く"><div class="idea-art">${artFor(x)}<span class="card-badge">${x.generation===0?'ORIGIN':`GEN ${x.generation}`}</span></div><div class="idea-info"><h3>${escapeHTML(x.title)}</h3><p>${escapeHTML(short(x.prompt,35))}</p><div class="card-foot"><span><span class="avatar" style="background:${escapeHTML(x.author_color)}">${escapeHTML(x.author?.slice(0,1))}</span>${escapeHTML(x.author)}</span><span class="counter">♡ ${x.likes} &nbsp; ✦ ${x.supporters}</span></div></div></article>`).join('') || '<p>一致する作品がありません。キーワードを変えてください。</p>';
  $('moreIdeas').style.display=data.length<=state.shown?'none':'inline-flex';
}
function openDrawer(content) { $('drawerBody').innerHTML=content; $('overlay').hidden=false;document.body.style.overflow='hidden';$('drawerTitle')?.focus?.() }
function closeDrawer(){ $('overlay').hidden=true;document.body.style.overflow='';state.selected=null }
function renderDetail(idea, open=true) {
  state.selected=idea.id;
  const html=`<div class="page-eyebrow">GENERATION ${idea.generation} · CO-CREATION</div><h2 id="drawerTitle">${escapeHTML(idea.title)}</h2><div class="detail-art idea-art">${artFor(idea)}</div><div class="detail-meta"><span>${escapeHTML(idea.author)} の作品</span><span>${escapeHTML(idea.category)}</span><span>♡ ${idea.likes} likes</span><span>✦ ${idea.support_points} 応援ポイント（模擬）</span></div><h3>このアイデアの背景</h3><p>${escapeHTML(idea.prompt)}</p><div class="lineage">${idea.parent_id?`継承元：${escapeHTML(parentName(idea))}`:'ここから進化がはじまりました。'}<br>作品の系譜は次の人のアイデアへとつながります。</div><div class="detail-row"><button class="button primary" data-action="remix" data-id="${escapeHTML(idea.id)}">↗ この作品を継承する</button><button class="button secondary" data-action="like" data-id="${escapeHTML(idea.id)}">${idea.liked?'♥ いいね済み':'♡ いいね'}</button></div><div class="form-row"><label for="pledgePoints">応援したい気持ちを登録する（仮想ポイント）</label><select id="pledgePoints"><option value="10">10 ポイント</option><option value="50">50 ポイント</option><option value="100">100 ポイント</option></select><button class="button ghost" data-action="pledge" data-id="${escapeHTML(idea.id)}">✦ 応援意思を登録</button><span class="mini">※ エポスポイントや金銭の決済・差引は行われません。</span></div><h3>ファンからのコメント</h3><div id="commentsPanel">読み込み中…</div><form id="commentForm" data-id="${escapeHTML(idea.id)}"><div class="form-row"><label for="commentText">コメントを投稿</label><textarea id="commentText" maxlength="400" required placeholder="気に入ったポイントや、改良したいアイデア"></textarea></div><button class="button secondary" type="submit">コメントを追加</button></form>`;
  if(open)openDrawer(html);else $('drawerBody').innerHTML=html;
  api(`/api/ideas/${idea.id}/comments`).then(({comments})=>{if(state.selected!==idea.id)return;$('commentsPanel').innerHTML=comments.map(c=>`<div class="comment"><b>${escapeHTML(c.name)}：</b>${escapeHTML(c.body)}</div>`).join('')||'<p class="mini">まだコメントはありません。</p>'}).catch(e=>toast(e.message));
}
function showCreate(parentId=null) {
  state.selected=null;
  const parent=state.map.get(parentId);
  const html=`<div class="page-eyebrow">CREATE · EVOLVE · DISCOVER</div><h2 id="drawerTitle">${parent?'この作品を、あなたならどう進化させる？':'あなたの「好き」から、はじめよう。'}</h2>${parent?`<p>継承元：<strong>${escapeHTML(parent.title)}</strong></p><div class="detail-art idea-art">${artFor(parent)}</div>`:'<p>思いがけない作品は、小さなひらめきから。画像生成がなくてもアイデアを投稿できます。</p>'}<form id="createForm" data-parent="${escapeHTML(parentId||'')}"><div class="form-row"><label for="ideaTitle">作品タイトル</label><input id="ideaTitle" required maxlength="80" minlength="2" placeholder="星降るクラゲのルームライト"></div><div class="form-row"><label for="ideaPrompt">どんな「欲しいっ！」ですか？</label><textarea id="ideaPrompt" required minlength="4" maxlength="600" placeholder="透明感のある青いガラス。夜にそっと光って、部屋に海を感じられるように…">${parent?escapeHTML(`「${parent.title}」から受け継ぎ、`):''}</textarea></div><div class="form-row"><label for="ideaCategory">商品カテゴリ</label><select id="ideaCategory"><option>インテリア</option><option>アクセサリー</option><option>雑貨</option><option>ぬいぐるみ</option><option>ファッション</option><option>文具</option><option>その他</option></select></div><div class="form-row"><label for="ideaMood">デザインの方向性</label><input id="ideaMood" maxlength="60" value="幻想的" placeholder="透明感、日常使い、上品"></div><div class="form-row"><label><input type="checkbox" class="checkbox" id="rightsCheck" required> 自分が権利を持つオリジナル作品であり、第三者の無許諾IPを含まないことを確認しました</label></div><div class="form-row"><label><input type="checkbox" class="checkbox" id="aiCheck"> OpenAI APIで商品画像を生成する（利用料金が発生する場合があります）</label><span class="mini">チェックを入れない場合はイラスト見本を表示します。AI実行にはサーバー側のAPI設定が必要です。</span></div><button class="button primary" type="submit" style="width:100%">✳ アイデアを投稿して進化させる</button></form>`;
  openDrawer(html);
}
function setTab(tab){state.tab=tab;document.querySelectorAll('.tabview').forEach(el=>el.classList.toggle('active',el.id===tab));document.querySelectorAll('[data-tab]').forEach(el=>el.classList.toggle('active',el.dataset.tab===tab));window.scrollTo({top:0,behavior:'smooth'});if(tab==='insights')renderInsights();if(tab==='picsy')renderPicsy();}
async function renderInsights(){try{const data=await api('/api/insights');for(const [id,list] of [['categoryBars',data.categories],['moodBars',data.moods]]){const max=Math.max(1,...list.map(x=>x.count));$(id).innerHTML=list.map(x=>`<div class="barrow"><span class="label">${escapeHTML(x.label)}</span><span class="track"><span class="fill" style="display:block;width:${x.count/max*100}%"></span></span><b>${x.count}</b></div>`).join('')};$('topIdeas').innerHTML=data.popular.map((x,i)=>`<div class="topline"><b>${i+1}. ${escapeHTML(x.title)}</b><span>♡ ${x.likes} · ✦ ${x.support_points} ポイント（模擬）</span></div>`).join('')}catch(e){toast(e.message)}}
async function renderPicsy(){try{const data=await api('/api/picsy');$('picsyBars').innerHTML=data.actors.map((n,i)=>`<div class="picsy-value"><span>${escapeHTML(n)}</span><b>${data.before.c[i].toFixed(3)} → ${data.after.c[i].toFixed(3)}</b></div><div class="barrow"><span class="track"><span class="fill" style="display:block;width:${Math.min(100,data.after.c[i]/1.5*100)}%"></span></span></div>`).join('')}catch(e){toast(e.message)}}
// Canvas lineage map; animation intentionally non-deterministic to avoid repetitive camera travel.
const canvas=$('graph'),ctx=canvas.getContext('2d');let W=0,H=0,positions=new Map();
function fitCanvas(){const rect=canvas.getBoundingClientRect(),dpi=Math.min(devicePixelRatio||1,2);W=rect.width;H=rect.height;canvas.width=Math.round(W*dpi);canvas.height=Math.round(H*dpi);ctx.setTransform(dpi,0,0,dpi,0,0)}
function positionNodes(){positions=new Map();const xs=state.ideas;xs.forEach((node,i)=>{let x,y;if(i===0){x=0;y=0}else{const depth=Math.min(7,node.generation),r=92+Math.sqrt(i)*51,ang=i*2.399963+Math.sin(i)*.12;x=Math.cos(ang)*r + depth*12;y=Math.sin(ang)*r*.69}positions.set(node.id,{x,y})})}
function offset(){return {x:W>800?W*.79:W*.72,y:H*.55}}
function screenOf(p){const o=offset(),c=state.camera;return {x:o.x+(p.x+c.x)*c.s,y:o.y+(p.y+c.y)*c.s}}
function draw(t){requestAnimationFrame(draw);if(!W)return;const delta=Math.min(.04,(t-(state.frame||t))/1000);state.frame=t;ctx.clearRect(0,0,W,H);positionNodes();const xs=state.ideas;ctx.save();for(const node of xs){if(!node.parent_id)continue;const p=positions.get(node.id),q=positions.get(node.parent_id);if(!p||!q)continue;const a=screenOf(p),b=screenOf(q);if(Math.max(a.x,b.x)<-50||Math.min(a.x,b.x)>W+50||Math.max(a.y,b.y)<-50||Math.min(a.y,b.y)>H+50)continue;ctx.beginPath();ctx.moveTo(b.x,b.y);ctx.quadraticCurveTo((a.x+b.x)/2,(a.y+b.y)/2-25*state.camera.s,a.x,a.y);ctx.strokeStyle='rgba(67,150,234,.25)';ctx.lineWidth=1.3;ctx.stroke()}
 for(const [i,node] of xs.entries()){const p=positions.get(node.id);if(!p)continue;const s=screenOf(p);if(s.x<-45||s.x>W+45||s.y<-45||s.y>H+45)continue;const selected=state.selected===node.id,r=Math.max(3,Math.min(18,(4.5+Math.min(node.likes,16)*.9)*state.camera.s));ctx.beginPath();ctx.arc(s.x,s.y,r+7+Math.sin(t/650+i)*1.7,0,Math.PI*2);ctx.fillStyle=selected?'rgba(32,117,248,.24)':'rgba(53,143,241,.07)';ctx.fill();ctx.beginPath();ctx.arc(s.x,s.y,r,0,Math.PI*2);ctx.fillStyle=palette[i%palette.length];ctx.fill();ctx.lineWidth=selected?3:1.5;ctx.strokeStyle='#fff';ctx.stroke();ctx.beginPath();ctx.arc(s.x-r*.26,s.y-r*.23,r*.27,0,Math.PI*2);ctx.fillStyle='#ffffffa8';ctx.fill()}
 ctx.restore()}
function hit(x,y){let chosen=null,dist=25;for(const [id,p] of positions){const s=screenOf(p),d=Math.hypot(s.x-x,s.y-y);if(d<dist){dist=d;chosen=id}}return chosen}
function animateTo(id){const target=positions.get(id);if(!target)return;const c=state.camera,from={...c},to={x:-target.x,y:-target.y,s:1.45+Math.random()*.9},duration=600+Math.random()*1000,start=performance.now(),easing=Math.random()>.5?'spring':'cubic';function tick(now){const v=Math.min(1,(now-start)/duration),e=easing==='cubic'?(1-(1-v)**3):1-Math.cos(v*Math.PI*.5)*(1-v);c.x=from.x+(to.x-from.x)*e;c.y=from.y+(to.y-from.y)*e;c.s=from.s+(to.s-from.s)*e;if(v<1)requestAnimationFrame(tick)}requestAnimationFrame(tick)}
canvas.addEventListener('pointerdown',e=>{state.pointer={x:e.clientX,y:e.clientY,cx:state.camera.x,cy:state.camera.y,moved:false};canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener('pointermove',e=>{const p=state.pointer;if(!p)return;const dx=e.clientX-p.x,dy=e.clientY-p.y;if(Math.abs(dx)+Math.abs(dy)>5)p.moved=true;state.camera.x=p.cx+dx/state.camera.s;state.camera.y=p.cy+dy/state.camera.s});
canvas.addEventListener('pointerup',e=>{const p=state.pointer;state.pointer=null;if(!p?.moved){const rect=canvas.getBoundingClientRect(),id=hit(e.clientX-rect.left,e.clientY-rect.top);if(id){animateTo(id);renderDetail(state.map.get(id))}}});
canvas.addEventListener('wheel',e=>{e.preventDefault();state.camera.s=Math.max(.38,Math.min(4,state.camera.s*(e.deltaY<0?1.12:.89)))},{passive:false});
$('zoomIn').onclick=()=>state.camera.s=Math.min(4,state.camera.s*1.25);$('zoomOut').onclick=()=>state.camera.s=Math.max(.38,state.camera.s*.8);$('resetView').onclick=()=>{state.camera={x:0,y:0,s:1}};
$('randomTravel').onclick=()=>{const xs=state.ideas;if(!xs.length)return;const x=xs[Math.floor(Math.random()*xs.length)];animateTo(x.id);renderDetail(x)};
$('userSelect').value=state.user;$('userSelect').onchange=async e=>{state.user=e.target.value;localStorage.setItem('zoku-user',state.user);await refresh()};
$('openCreate').onclick=()=>showCreate();$('heroCreate').onclick=()=>showCreate();document.querySelectorAll('[data-tab]').forEach(el=>el.onclick=()=>setTab(el.dataset.tab));$('searchIdeas').oninput=e=>{state.search=e.target.value;state.shown=12;renderGrid()};$('sortIdeas').onchange=e=>{state.sort=e.target.value;renderGrid()};$('moreIdeas').onclick=()=>{state.shown+=12;renderGrid()};
document.addEventListener('click',async e=>{if(e.target.closest('[data-close]')){closeDrawer();return}const open=e.target.closest('[data-open]');if(open){const i=state.map.get(open.dataset.open);if(i){renderDetail(i);animateTo(i.id)}return}const action=e.target.closest('[data-action]');if(!action)return;const id=action.dataset.id;try{if(action.dataset.action==='remix'){showCreate(id);return}if(action.dataset.action==='like'){await api(`/api/ideas/${id}/like`,{method:'POST',body:'{}'});await refresh();toast('あなたの好きが届きました ♡')}if(action.dataset.action==='pledge'){const n=Number($('pledgePoints').value);await api(`/api/ideas/${id}/pledge`,{method:'POST',body:JSON.stringify({points:n})});await refresh();toast('応援意思を記録しました（実際の支払なし）')}}catch(err){toast(err.message)}});
document.addEventListener('submit',async e => {
  if(e.target.id === 'createForm') {
    e.preventDefault();
    const f=e.target;
    const button=f.querySelector('button[type=submit]');
    const withAI=$('aiCheck').checked;
    button.disabled=true;
    button.textContent='アイデアを登録しています…';
    try {
      const data={title:$('ideaTitle').value,prompt:$('ideaPrompt').value,
        parent_id:f.dataset.parent||null,category:$('ideaCategory').value,
        mood:$('ideaMood').value,rights:'original'};
      const {id}=await api('/api/ideas',{method:'POST',body:JSON.stringify(data)});
      closeDrawer();
      await refresh();
      const idea=state.map.get(id);
      if(idea){renderDetail(idea);animateTo(id)}
      toast('新しい「好き」が生まれました！');
      if(withAI) {
        toast('画像を生成しています。課金が発生する場合があります。');
        try {
          await api(`/api/ideas/${id}/generate`,{method:'POST',body:'{}'});
          await refresh();
          toast('商品画像が完成しました！');
        } catch(err) { toast('アイデアは保存済み。画像生成：'+err.message) }
      }
    } catch(err) { toast(err.message) }
    finally {
      button.disabled=false;
      button.textContent='✳ アイデアを投稿して進化させる';
    }
  }
  if(e.target.id === 'commentForm') {
    e.preventDefault();
    const id=e.target.dataset.id, body=$('commentText').value;
    try {
      await api(`/api/ideas/${id}/comment`,{method:'POST',body:JSON.stringify({body})});
      renderDetail(state.map.get(id));
      toast('コメントを追加しました');
    } catch(err) { toast(err.message) }
  }
});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('overlay').hidden)closeDrawer();const open=e.target.closest('[data-open]');if(open&&(e.key==='Enter'||e.key===' ')){e.preventDefault();renderDetail(state.map.get(open.dataset.open))}});
(async function start(){fitCanvas();window.addEventListener('resize',fitCanvas);requestAnimationFrame(draw);try{await refresh();toast('共創マップを読み込みました。作品をクリックして探索できます。')}catch(e){toast('データ取得に失敗：'+e.message)}setInterval(async()=>{try{const {seq}=await api('/api/events');if(seq!==state.seq)await refresh(true)}catch(e){$('syncedLabel').textContent='再接続待ち'}},4000)})();
