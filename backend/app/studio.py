"""
Web creator studio (/studio) — the creator surface on the web, mirroring the iOS
app. A single self-contained page + vanilla JS that talks to the existing JSON
API with a Bearer token kept in localStorage:

  sign in (email)      -> POST /auth/dev-login
  become a creator     -> POST /me/become-creator
  list pages           -> GET  /me/pages
  new page from a link -> POST /me/generate {url}  + poll /me/generate/{id}
  edit page text       -> PATCH /me/pages/{slug}
  archive / delete     -> POST /me/pages/{slug}/(un)archive · DELETE /me/pages/{slug}

Auth note: this reuses the same email dev-login the app uses — fine for a demo,
but it is NOT real authentication (no password). Behind a managed provider
(AUTH_PROVIDER=oidc) you'd swap the login step for the provider's flow.
"""

from __future__ import annotations

from app import config

BASE = config.PUBLIC_BASE_URL


def studio_html() -> str:
    return _STUDIO.replace("{{BRAND}}", config.BRAND).replace("{{BASE}}", BASE)


_STUDIO = r"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Creator Studio · {{BRAND}}</title>
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#FFE566;--sun:#FFD84D;--ink:#201B0A;--grey:#7A6F4A;--faint:#B4A98A;--line:rgba(32,27,10,.14);--soft:#FBF7E6;--cream:#fff;--surface:#fff;--accent:#6F5DF0;--accent-deep:#5A47E0;--accent-soft:#ECE8FE;--red:#D64545}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Instrument Sans',-apple-system,sans-serif;color:var(--ink);line-height:1.55;background:radial-gradient(circle at 18% 10%,#FFF3A8 0%,transparent 46%),radial-gradient(circle at 85% 92%,#FFD23E 0%,transparent 52%),var(--bg)}
a{color:inherit}
.bar{background:rgba(255,255,255,.7);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}
.bar .in{max-width:820px;margin:0 auto;padding:0 22px;height:60px;display:flex;align-items:center;justify-content:space-between}
.brand{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:21px;letter-spacing:-.5px;text-decoration:none}.brand .d{color:var(--accent)}
.wrap{max-width:820px;margin:0 auto;padding:34px 22px 80px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:22px;margin-bottom:16px;box-shadow:0 6px 16px rgba(32,27,10,.06)}
h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:34px;letter-spacing:-.5px;margin-bottom:8px}
h2{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:20px;margin-bottom:14px}
.sub{color:var(--grey);margin-bottom:22px}
label{display:block;font-size:12.5px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:var(--grey);margin:14px 0 6px}
input,textarea{width:100%;font:inherit;font-size:15px;padding:13px 15px;border:1px solid var(--line);border-radius:13px;background:var(--surface);color:var(--ink);outline:none}
input:focus,textarea:focus{border-color:var(--accent);box-shadow:0 0 0 4px rgba(111,93,240,.16)}
textarea{resize:vertical;min-height:64px}
.btn{display:inline-flex;align-items:center;gap:7px;border:none;cursor:pointer;font:inherit;font-weight:700;font-size:14.5px;padding:12px 20px;border-radius:999px;background:var(--accent);color:#fff;box-shadow:0 8px 20px rgba(90,71,224,.35)}
.btn:disabled{opacity:.5;cursor:default}
.btn.ink{background:var(--ink);color:#fff}.btn.ghost{background:#fff;border:1.5px solid var(--line);color:var(--ink);font-weight:600}
.btn.sm{padding:9px 15px;font-size:13px;border-radius:999px}
.btn.danger{color:var(--red);background:#fff;border:1.5px solid var(--line)}
.row{display:flex;gap:9px;flex-wrap:wrap;align-items:center}
.muted{color:var(--grey);font-size:13.5px}
.err{color:var(--red);font-size:13.5px;margin-top:10px}
.pill{font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;padding:3px 9px;border-radius:999px;background:var(--soft);color:var(--grey)}
.pill.live{background:#E8F6EC;color:#2C8C4A}.pill.arch{background:#F2E9E4;color:#9A6A4A}
.pg{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 0;border-top:1px solid var(--line)}
.pg:first-child{border-top:none}
.pg .t{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:18px}
.pg .l{font-size:12.5px;color:var(--grey)}
.pg .l a{color:var(--accent-deep);border-bottom:2px solid var(--accent);text-decoration:none;font-weight:600}
.prod{border-top:1px dashed var(--line);padding-top:12px;margin-top:12px}
.prod .pn{font-weight:600;font-size:13px;color:var(--grey);margin-bottom:6px}
.hide{display:none}
.spin{display:inline-block;width:15px;height:15px;border:2px solid var(--line);border-top-color:var(--ink);border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px}
@keyframes sp{to{transform:rotate(360deg)}}
</style></head>
<body>
<div class="bar"><div class="in"><a class="brand" href="{{BASE}}">{{BRAND}}<span class="d">.</span></a>
<div class="row" id="whoami"></div></div></div>
<div class="wrap" id="app"><p class="muted">Loading…</p></div>

<script>
var BASE = window.location.origin;
var tok = localStorage.getItem('reelie.token') || '';
var me = null; try { me = JSON.parse(localStorage.getItem('reelie.user')||'null'); } catch(e){}
var app = document.getElementById('app'), who = document.getElementById('whoami');

function esc(s){ return (s||'').replace(/[&<>"]/g, function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }

async function api(method, path, body){
  var h = {'Content-Type':'application/json'};
  if(tok) h['Authorization'] = 'Bearer '+tok;
  var r = await fetch(BASE+path, {method:method, headers:h, body: body?JSON.stringify(body):undefined});
  if(r.status===401){ signOut(); throw new Error('Please sign in again.'); }
  var txt = await r.text(); var data = txt?JSON.parse(txt):null;
  if(!r.ok) throw new Error((data && (data.detail||data.error)) || ('Error '+r.status));
  return data;
}
function setSession(t, u){ tok=t; me=u; localStorage.setItem('reelie.token',t); localStorage.setItem('reelie.user',JSON.stringify(u)); }
function signOut(){ tok=''; me=null; localStorage.removeItem('reelie.token'); localStorage.removeItem('reelie.user'); render(); }

function header(){
  if(me && tok){ who.innerHTML = '<span class="muted">'+esc(me.handle?('@'+me.handle):me.email)+'</span> <button class="btn ghost sm" onclick="signOut()">Sign out</button>'; }
  else { who.innerHTML = ''; }
}

// ---- views ----
function viewLogin(){
  app.innerHTML =
   '<h1>Creator Studio</h1><p class="sub">Sign in to turn your videos into shoppable, AI-discoverable pages.</p>'+
   '<div class="card" style="max-width:440px">'+
   '<label>Email</label><input id="email" type="email" placeholder="you@example.com" autocomplete="email">'+
   '<div style="height:14px"></div><button class="btn" id="go">Continue</button>'+
   '<div class="err hide" id="err"></div></div>';
  document.getElementById('go').onclick = doLogin;
  document.getElementById('email').addEventListener('keydown',function(e){ if(e.key==='Enter') doLogin(); });
}
async function doLogin(){
  var email = document.getElementById('email').value.trim(), err=document.getElementById('err');
  if(!email || email.indexOf('@')<0){ err.textContent='Enter a valid email.'; err.classList.remove('hide'); return; }
  err.classList.add('hide');
  try { var r = await api('POST','/auth/dev-login',{email:email}); setSession(r.token, r.user); render(); }
  catch(e){ err.textContent=e.message; err.classList.remove('hide'); }
}

function viewBecomeCreator(){
  app.innerHTML =
   '<h1>Claim your page</h1><p class="sub">Pick a handle — it\'s the link you\'ll share in your videos.</p>'+
   '<div class="card" style="max-width:440px">'+
   '<label>Handle</label><input id="handle" placeholder="yourname" autocomplete="off">'+
   '<div style="height:14px"></div><button class="btn" id="go">Claim &amp; continue</button>'+
   '<div class="err hide" id="err"></div></div>';
  document.getElementById('go').onclick = async function(){
    var h=document.getElementById('handle').value.trim().toLowerCase().replace(/^@/,''), err=document.getElementById('err');
    if(h.length<3){ err.textContent='Pick a handle (3+ characters).'; err.classList.remove('hide'); return; }
    err.classList.add('hide');
    try { var u = await api('POST','/me/become-creator',{handle:h, displayName: me.displayName||h, platforms:[]}); setSession(tok,u); render(); }
    catch(e){ err.textContent=e.message; err.classList.remove('hide'); }
  };
}

async function viewDashboard(){
  app.innerHTML = '<h1>Your pages</h1><p class="sub">Generate a page from a video link, then edit or manage it.</p>'+
   '<div class="card"><h2>New page from a link</h2>'+
   '<input id="url" placeholder="YouTube, TikTok, or a video URL">'+
   '<div style="height:10px"></div>'+
   '<input id="ptitle" placeholder="Page name (optional — defaults to the video title)">'+
   '<div style="height:12px"></div><button class="btn" id="gen">Make page</button>'+
   '<div class="muted" id="genstatus" style="margin-top:10px"></div></div>'+
   '<div class="card" id="pages"><p class="muted">Loading your pages…</p></div>';
  document.getElementById('gen').onclick = doGenerate;
  loadPages();
}

async function loadPages(){
  var box = document.getElementById('pages');
  try {
    var pages = await api('GET','/me/pages');
    if(!pages.length){ box.innerHTML='<h2>Pages</h2><p class="muted">No pages yet — make one from a link above.</p>'; return; }
    box.innerHTML = '<h2>Pages ('+pages.length+')</h2>' + pages.map(pageRow).join('');
  } catch(e){ box.innerHTML='<p class="err">'+esc(e.message)+'</p>'; }
}

function pageRow(p){
  var live = !p.archived;
  return '<div class="pg" id="row-'+esc(p.slug)+'"><div>'+
    '<div class="t">'+esc(p.title)+' <span class="pill '+(live?'live':'arch')+'">'+(live?'Live':'Archived')+'</span></div>'+
    '<div class="l"><a href="{{BASE}}/'+esc(p.handle)+'/'+esc(p.slug)+'" target="_blank">reelie.shop/'+esc(p.handle)+'/'+esc(p.slug)+' →</a> · '+p.products.length+' products</div>'+
    '</div><div class="row">'+
    '<button class="btn ghost sm" onclick="toggleEdit(\''+esc(p.slug)+'\')">Edit</button>'+
    '<button class="btn ghost sm" onclick="archive(\''+esc(p.slug)+'\','+(live?'true':'false')+')">'+(live?'Archive':'Unarchive')+'</button>'+
    '<button class="btn danger sm" onclick="del(\''+esc(p.slug)+'\')">Delete</button>'+
    '</div></div>'+
    '<div class="hide" id="edit-'+esc(p.slug)+'"></div>';
}

var CACHE = {};
async function toggleEdit(slug){
  var box = document.getElementById('edit-'+slug);
  if(!box.classList.contains('hide')){ box.classList.add('hide'); box.innerHTML=''; return; }
  var pages = await api('GET','/me/pages'); var p = pages.find(function(x){return x.slug===slug;}); CACHE[slug]=p;
  box.innerHTML =
    '<div class="card" style="margin-top:2px">'+
    '<label>Title</label><input id="t-'+slug+'" value="'+esc(p.title)+'">'+
    '<label>Intro</label><textarea id="i-'+slug+'">'+esc(p.intro||'')+'</textarea>'+
    '<label>Disclosure</label><textarea id="d-'+slug+'">'+esc(p.disclosure||'')+'</textarea>'+
    p.products.map(function(pr){ return '<div class="prod"><div class="pn">Product '+pr.position+' — '+esc(pr.brand||'')+'</div>'+
        '<label>Name</label><input id="pn-'+slug+'-'+pr.id+'" value="'+esc(pr.name)+'">'+
        '<label>Note</label><input id="pnote-'+slug+'-'+pr.id+'" value="'+esc(pr.note||'')+'"></div>'; }).join('')+
    '<div style="height:14px"></div><button class="btn" onclick="saveEdit(\''+slug+'\')">Save changes</button>'+
    '<span class="muted" id="save-'+slug+'" style="margin-left:10px"></span></div>';
  box.classList.remove('hide');
}
async function saveEdit(slug){
  var p = CACHE[slug], st=document.getElementById('save-'+slug); st.textContent='Saving…';
  var body = { title: val('t-'+slug), intro: val('i-'+slug), disclosure: val('d-'+slug),
    products: p.products.map(function(pr){ return { id:pr.id, name: val('pn-'+slug+'-'+pr.id), note: val('pnote-'+slug+'-'+pr.id) }; }) };
  try { await api('PATCH','/me/pages/'+slug, body); st.textContent='Saved ✓'; setTimeout(loadPages, 600); }
  catch(e){ st.textContent=e.message; }
}
function val(id){ var el=document.getElementById(id); return el?el.value:null; }

async function archive(slug, live){ await api('POST','/me/pages/'+slug+'/'+(live?'archive':'unarchive')); loadPages(); }
async function del(slug){ if(!confirm('Delete this page? This cannot be undone.')) return; await api('DELETE','/me/pages/'+slug); loadPages(); }

async function doGenerate(){
  var url = document.getElementById('url').value.trim(), st=document.getElementById('genstatus'), btn=document.getElementById('gen');
  var title = document.getElementById('ptitle').value.trim();
  if(!url){ st.textContent='Paste a video link first.'; return; }
  btn.disabled=true; st.innerHTML='<span class="spin"></span> Starting…';
  try {
    var r = await api('POST','/me/generate',{url:url, title:title||undefined}); var job=r.jobId;
    for(var i=0;i<200;i++){
      await new Promise(function(res){setTimeout(res,3000);});
      var s = await api('GET','/me/generate/'+job);
      st.innerHTML = '<span class="spin"></span> '+esc(s.stage||s.status);
      if(s.status==='done'){ st.textContent='Published ✓'; document.getElementById('url').value=''; loadPages(); break; }
      if(s.status==='error'){ st.innerHTML='<span class="err">'+esc(s.error||'Failed')+'</span>'; break; }
    }
  } catch(e){ st.innerHTML='<span class="err">'+esc(e.message)+'</span>'; }
  btn.disabled=false;
}

async function render(){
  header();
  if(!tok){ viewLogin(); return; }
  // refresh identity so role is current
  try { me = await api('GET','/me'); localStorage.setItem('reelie.user', JSON.stringify(me)); }
  catch(e){ signOut(); return; }
  header();
  var isCreator = me.role==='creator' || me.role==='both';
  if(isCreator && me.handle) viewDashboard(); else viewBecomeCreator();
}
render();
</script>
</body></html>"""
