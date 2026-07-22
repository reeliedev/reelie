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
.btn.oauth{width:100%;justify-content:center;margin-bottom:10px}
.btn.apple{background:#111;color:#fff;box-shadow:none}
.btn.google{background:#fff;color:var(--ink);border:1.5px solid var(--line);box-shadow:none}
.hr{display:flex;align-items:center;text-align:center;color:var(--faint);font-size:12px;font-weight:600;margin:14px 0}
.hr::before,.hr::after{content:"";flex:1;height:1px;background:var(--line)}.hr span{padding:0 12px}
.btn.sm{padding:9px 15px;font-size:13px;border-radius:999px}
.btn.danger{color:var(--red);background:#fff;border:1.5px solid var(--line)}
.row{display:flex;gap:9px;flex-wrap:wrap;align-items:center}
.muted{color:var(--grey);font-size:13.5px}
.err{color:var(--red);font-size:13.5px;margin-top:10px}
.pill{font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;padding:3px 9px;border-radius:999px;background:var(--soft);color:var(--grey)}
.pill.live{background:#E8F6EC;color:#2C8C4A}.pill.arch{background:#F2E9E4;color:#9A6A4A}
.pill.draft{background:#FBF0D6;color:#9A7A18}
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
.tabs{display:flex;gap:8px;margin-bottom:12px}
.tab{background:#fff;border:1.5px solid var(--line);color:var(--grey);font-weight:600;font-size:14px;padding:8px 14px;border-radius:999px;cursor:pointer;font-family:inherit}
.tab.on{border-color:var(--ink);color:var(--ink);background:var(--wash,#faf7ef)}
.tab .hint{font-weight:500;font-size:11px;color:var(--accent-deep);margin-left:5px}
input[type=file]{padding:9px 12px}
/* live analysis view */
.az{max-width:860px;margin:0 auto;padding-top:6px}
.az-head{text-align:center;margin-bottom:24px}
.az-dotwrap{height:16px}
.az-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--accent);animation:azpulse 1.4s infinite}
@keyframes azpulse{0%{box-shadow:0 0 0 0 rgba(111,93,240,.45)}70%{box-shadow:0 0 0 11px rgba(111,93,240,0)}100%{box-shadow:0 0 0 0 rgba(111,93,240,0)}}
.az-head h1{font-size:26px}
.az-sub{color:var(--grey);font-size:14.5px;min-height:20px;transition:opacity .3s}
.az-body{display:grid;grid-template-columns:1.05fr .95fr;gap:22px;align-items:start}
@media(max-width:720px){.az-body{grid-template-columns:1fr}}
.az-stage{position:relative;border-radius:18px;overflow:hidden;background:#0c0a05;aspect-ratio:9/16;max-height:min(58vh,560px);margin:0 auto;width:100%;box-shadow:0 10px 30px rgba(32,27,10,.14)}
.az-vid{width:100%;height:100%;object-fit:cover;display:block}
.az-ph{display:flex;align-items:center;justify-content:center;font-size:66px;background:linear-gradient(135deg,#2a2740,#171528)}
.az-scan{position:absolute;left:0;right:0;top:0;height:32%;pointer-events:none;
  background:linear-gradient(180deg,rgba(124,108,255,0),rgba(124,108,255,.12) 68%,rgba(150,135,255,.5));
  border-bottom:2px solid rgba(176,162,255,.95);animation:azscan 2.6s cubic-bezier(.55,0,.45,1) infinite}
@keyframes azscan{0%{transform:translateY(-38%)}50%{transform:translateY(210%)}100%{transform:translateY(-38%)}}
.az-grid{position:absolute;inset:0;pointer-events:none;opacity:.14;
  background-image:linear-gradient(rgba(176,162,255,.6) 1px,transparent 1px),linear-gradient(90deg,rgba(176,162,255,.6) 1px,transparent 1px);
  background-size:34px 34px}
.az-stage.ping{animation:azping .55s}
@keyframes azping{0%{box-shadow:inset 0 0 0 0 rgba(176,162,255,0),0 10px 30px rgba(32,27,10,.14)}
  30%{box-shadow:inset 0 0 0 4px rgba(176,162,255,.95),0 10px 30px rgba(32,27,10,.14)}
  100%{box-shadow:inset 0 0 0 0 rgba(176,162,255,0),0 10px 30px rgba(32,27,10,.14)}}
.az-count{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:16px;color:var(--ink);margin-bottom:14px}
.az-list{display:flex;flex-direction:column;gap:9px;max-height:56vh;overflow:auto}
.az-item{display:flex;gap:11px;align-items:center;padding:11px 13px;border:1.5px solid var(--line);border-radius:13px;background:#fff;
  opacity:0;transform:translateY(9px) scale(.96);transition:all .5s cubic-bezier(.2,.85,.25,1)}
.az-item.in{opacity:1;transform:none;border-color:#d9d2f7;box-shadow:0 5px 16px rgba(111,93,240,.12)}
.az-em{font-size:18px}
.az-nm{font-weight:600;font-size:14px;color:var(--ink);line-height:1.25}
.az-var{color:var(--grey);font-weight:500;font-size:12.5px}
.az-ts{font-size:11.5px;color:var(--accent-deep);font-weight:600;margin-top:2px;text-transform:capitalize}
.az-foot{text-align:center;margin-top:28px}
/* product review + full editor */
.rv{max-width:640px;margin:0 auto}
.rv-head{text-align:center;margin-bottom:22px}
.rv-head h1{font-size:26px}
.rv-prod{border:1.5px solid var(--line);border-radius:14px;background:#fff;margin-bottom:10px;overflow:hidden}
.rv-prod[open]{border-color:#d9d2f7;box-shadow:0 5px 16px rgba(111,93,240,.10)}
.rv-prod summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:11px;padding:14px 15px;font-weight:600}
.rv-prod summary::-webkit-details-marker{display:none}
.rv-em{font-size:18px}
.rv-t{flex:1;font-size:14.5px;color:var(--ink)}
.rv-chev{color:var(--grey);font-size:13px;transition:transform .2s}
.rv-prod[open] .rv-chev{transform:rotate(180deg)}
.rv-fields{padding:2px 15px 16px}
.rv-fields label{display:block;font-size:12px;font-weight:600;color:var(--grey);margin:10px 0 4px}
.rv-actions{display:flex;gap:10px;margin-top:22px}
.rv-actions .btn{flex:1}
.eh{font-family:'Space Grotesk',sans-serif;font-size:18px;margin:26px 0 12px}
.faq-gen{border-left:3px solid var(--accent-soft);padding:4px 0 4px 14px;margin-bottom:14px}
.faq-gen .faq-q{font-weight:600;font-size:14px;color:var(--ink)}
.faq-gen .faq-a{font-size:13.5px;color:var(--grey);margin-top:3px}
.faq-edit{border:1.5px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px}
.faq-edit input,.faq-edit textarea{margin-bottom:8px}
/* product review: video beside the editable cards */
.rv2{max-width:1000px;margin:0 auto}
.rv-split{display:grid;grid-template-columns:minmax(240px,340px) 1fr;gap:26px;align-items:start}
@media(max-width:760px){.rv-split{grid-template-columns:1fr}}
.rv-videocol{position:sticky;top:82px}
.rv-vid{width:100%;aspect-ratio:9/16;max-height:64vh;object-fit:cover;background:#0c0a05;border-radius:16px;display:block;box-shadow:0 10px 26px rgba(32,27,10,.14)}
.rv-vidph{display:flex;align-items:center;justify-content:center;font-size:56px;background:linear-gradient(135deg,#2a2740,#171528)}
.rv-editcol .rv-actions{margin-top:20px}
/* iframe WYSIWYG editor */
.ed-bar{position:sticky;top:56px;z-index:5;display:flex;align-items:center;gap:14px;background:rgba(255,255,255,.92);
  -webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);border:1px solid var(--line);border-radius:14px;
  padding:10px 14px;margin-bottom:14px;box-shadow:0 6px 16px rgba(32,27,10,.08)}
.ed-hint{flex:1;font-size:13px;color:var(--grey)}
.ed-chip{background:var(--accent-soft);color:var(--accent-deep);padding:1px 7px;border-radius:6px;font-weight:600}
.ed-frame{width:100%;height:calc(100vh - 150px);border:1px solid var(--line);border-radius:16px;background:#fff;box-shadow:0 6px 16px rgba(32,27,10,.06)}
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
// Capture the redirect params IMMEDIATELY (before supabase-js reads/clears the hash),
// so the login screen can report what came back after a magic-link/OAuth click.
var INIT_HASH = location.hash || '', INIT_SEARCH = location.search || '';

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
async function signOut(){ if(sb){ try{ await sb.auth.signOut(); }catch(e){} } tok=''; me=null; localStorage.removeItem('reelie.token'); localStorage.removeItem('reelie.user'); render(); }

// Auth provider: 'supabase' (Apple/Google/magic-link) when configured, else the
// local dev email login. The backend tells us which via /auth/config.
var AUTHCFG=null, sb=null;
async function authConfig(){ if(!AUTHCFG){ try{ AUTHCFG=await (await fetch('/auth/config')).json(); }catch(e){ AUTHCFG={provider:'dev'}; } } return AUTHCFG; }
function loadScript(src){ return new Promise(function(res,rej){ var s=document.createElement('script'); s.src=src; s.onload=res; s.onerror=rej; document.head.appendChild(s); }); }
async function supa(){
  if(sb) return sb;
  if(!window.supabase) await loadScript('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2');
  sb = window.supabase.createClient(AUTHCFG.supabaseUrl, AUTHCFG.supabaseAnonKey, {
    // implicit flow: magic-link/OAuth return the session in the URL hash — robust
    // to email link pre-scanning (PKCE needs a locally-stored verifier and breaks).
    auth: { flowType: 'implicit', detectSessionInUrl: true, persistSession: true, autoRefreshToken: true }
  });
  sb.auth.onAuthStateChange(function(evt, s){
    var t = (s && s.access_token) || '';
    if(t){
      // Session arrived (incl. after a magic-link / OAuth redirect is processed) —
      // if it's new, store it and re-render so we leave the login screen.
      if(t !== tok){ tok = t; localStorage.setItem('reelie.token', t); render(); }
    } else if(evt === 'SIGNED_OUT'){ tok = ''; }
  });
  return sb;
}

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

async function viewSupabaseLogin(){
  app.innerHTML =
   '<h1>Creator Studio</h1><p class="sub">Sign in to turn your videos into shoppable, AI-discoverable pages.</p>'+
   '<div class="card" style="max-width:420px">'+
   '<button class="btn oauth apple" id="apple"> Sign in with Apple</button>'+
   '<button class="btn oauth google" id="google"> Continue with Google</button>'+
   '<div class="hr"><span>or</span></div>'+
   '<label>Email</label><input id="email" type="email" placeholder="you@example.com" autocomplete="email">'+
   '<div style="height:12px"></div><button class="btn oauth" id="mlink">Send magic link</button>'+
   '<div class="muted" id="msg" style="margin-top:12px"></div></div>';
  // Diagnose: report exactly what the redirect brought back (from the captured URL).
  var hp = new URLSearchParams((INIT_HASH||'').replace(/^#/,'')), qp = new URLSearchParams(INIT_SEARCH||'');
  var authErr = hp.get('error_description') || qp.get('error_description') || hp.get('error') || qp.get('error');
  var keys = Array.from(new Set([].concat(Array.from(hp.keys()), Array.from(qp.keys()))));
  var msgEl = document.getElementById('msg');
  if(authErr){ msgEl.innerHTML = '<span class="err">'+esc(decodeURIComponent(authErr))+'</span>'; }
  else if(keys.length){ msgEl.innerHTML = '<span class="muted">redirect brought: '+esc(keys.join(', '))+'</span>'; }
  else { msgEl.innerHTML = '<span class="muted">redirect brought: (nothing)</span>'; }
  var c = await supa();
  document.getElementById('apple').onclick = function(){ c.auth.signInWithOAuth({provider:'apple', options:{redirectTo:location.href}}); };
  document.getElementById('google').onclick = function(){ c.auth.signInWithOAuth({provider:'google', options:{redirectTo:location.href}}); };
  document.getElementById('mlink').onclick = async function(){
    var email=document.getElementById('email').value.trim(), msg=document.getElementById('msg');
    if(email.indexOf('@')<1){ msg.textContent='Enter a valid email.'; return; }
    msg.textContent='Sending…';
    var r = await c.auth.signInWithOtp({email:email, options:{emailRedirectTo:location.href}});
    msg.textContent = r.error ? r.error.message : 'Check your email for a magic link ✨';
  };
  document.getElementById('email').addEventListener('keydown', function(e){ if(e.key==='Enter') document.getElementById('mlink').click(); });
}

function viewApply(){
  app.innerHTML =
   '<h1>Apply to the beta</h1><p class="sub">Reelie is invite-only while we onboard creators. Tell us where you post — we\'ll review and email you when you\'re in.</p>'+
   '<div class="card" style="max-width:460px">'+
   '<label>Your Reelie handle</label><input id="handle" placeholder="yourname" autocomplete="off">'+
   '<label>Instagram handle</label><input id="ig" placeholder="@yourinsta" autocomplete="off">'+
   '<label>YouTube handle</label><input id="yt" placeholder="@yourchannel" autocomplete="off">'+
   '<div style="height:16px"></div><button class="btn" id="go">Submit application</button>'+
   '<div class="err hide" id="err"></div></div>';
  document.getElementById('go').onclick = async function(){
    var h=document.getElementById('handle').value.trim().toLowerCase().replace(/^@/,''), err=document.getElementById('err');
    var ig=document.getElementById('ig').value.trim().replace(/^@/,''), yt=document.getElementById('yt').value.trim().replace(/^@/,'');
    if(h.length<3){ err.textContent='Pick a handle (3+ characters).'; err.classList.remove('hide'); return; }
    if(!ig && !yt){ err.textContent='Add at least one Instagram or YouTube handle.'; err.classList.remove('hide'); return; }
    err.classList.add('hide');
    try { var u = await api('POST','/me/become-creator',{handle:h, displayName: me.displayName||h, platforms:[], instagram:ig, youtube:yt}); setSession(tok,u); render(); }
    catch(e){ err.textContent=e.message; err.classList.remove('hide'); }
  };
}

function viewPending(){
  app.innerHTML =
   '<h1>Application received — under review</h1>'+
   '<div class="card" style="max-width:520px">'+
   '<p style="font-size:16px">Thanks, <b>@'+esc(me.handle)+'</b> ✨</p>'+
   '<p style="font-size:16px;margin-top:12px"><b>Please check your Instagram DMs.</b> We\'ll notify you via email'+
   (me.email?' at <b>'+esc(me.email)+'</b>':'')+
   ' when we\'ve sent you a DM on Instagram to complete the verification process.</p>'+
   '<div style="height:16px"></div><button class="btn ghost sm" onclick="render()">Refresh status</button></div>';
}

async function viewDashboard(){
  app.innerHTML = '<h1>Your pages</h1><p class="sub">Turn a video into a shoppable routine page, then edit or manage it.</p>'+
   '<div class="card"><h2>New page</h2>'+
   '<div class="tabs">'+
     '<button class="tab on" id="tab-link" onclick="pickTab(\'link\')">Paste a link</button>'+
     '<button class="tab" id="tab-upload" onclick="pickTab(\'upload\')">Upload video <span class="hint">best quality</span></button>'+
   '</div>'+
   '<div id="pane-link">'+
     '<input id="url" placeholder="YouTube, TikTok, or a video URL">'+
   '</div>'+
   '<div id="pane-upload" class="hide">'+
     '<input id="file" type="file" accept="video/mp4,video/quicktime,video/*">'+
     '<div class="muted" style="margin-top:6px">MP4 or MOV, up to ~500&nbsp;MB. Uploaded straight from your browser.</div>'+
   '</div>'+
   '<div style="height:10px"></div>'+
   '<input id="ptitle" placeholder="Page name (optional — defaults to the video title)">'+
   '<div style="height:12px"></div><button class="btn" id="gen">Make page</button>'+
   '<div class="muted" id="genstatus" style="margin-top:10px"></div></div>'+
   '<div class="card" id="pages"><p class="muted">Loading your pages…</p></div>';
  document.getElementById('gen').onclick = doGenerate;
  loadPages();
}

var GENTAB = 'link';
function pickTab(which){
  GENTAB = which;
  document.getElementById('tab-link').classList.toggle('on', which==='link');
  document.getElementById('tab-upload').classList.toggle('on', which==='upload');
  document.getElementById('pane-link').classList.toggle('hide', which!=='link');
  document.getElementById('pane-upload').classList.toggle('hide', which!=='upload');
  document.getElementById('genstatus').textContent='';
}
window.pickTab = pickTab;
function resetGenInputs(){
  var u=document.getElementById('url'); if(u) u.value='';
  var f=document.getElementById('file'); if(f) f.value='';
  var t=document.getElementById('ptitle'); if(t) t.value='';
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
  var archived = p.archived, published = (p.published !== false);
  var state = archived ? 'arch' : (published ? 'live' : 'draft');
  var badge = archived ? 'Archived' : (published ? 'Live' : 'Draft · review');
  var link = archived ? '{{BASE}}/'+esc(p.handle)+'/'+esc(p.slug)
                      : '{{BASE}}/'+esc(p.handle)+'/'+esc(p.slug);
  var linkText = published ? 'reelie.io/'+esc(p.handle)+'/'+esc(p.slug)+' →' : 'Preview draft →';
  var actions = '';
  if(!archived && !published)
    actions += '<button class="btn sm" onclick="publish(\''+esc(p.slug)+'\')">Approve &amp; Publish</button>';
  actions += '<button class="btn ghost sm" onclick="editFromDash(\''+esc(p.slug)+'\')">Edit</button>';
  if(!archived && published)
    actions += '<button class="btn ghost sm" onclick="unpublish(\''+esc(p.slug)+'\')">Unpublish</button>';
  actions += '<button class="btn ghost sm" onclick="archive(\''+esc(p.slug)+'\','+(archived?'false':'true')+')">'+(archived?'Unarchive':'Archive')+'</button>';
  actions += '<button class="btn danger sm" onclick="del(\''+esc(p.slug)+'\')">Delete</button>';
  return '<div class="pg" id="row-'+esc(p.slug)+'"><div>'+
    '<div class="t">'+esc(p.title)+' <span class="pill '+state+'">'+badge+'</span></div>'+
    '<div class="l"><a href="'+link+'" target="_blank">'+linkText+'</a> · '+p.products.length+' products</div>'+
    '</div><div class="row">'+ actions +
    '</div></div>'+
    '<div class="hide" id="edit-'+esc(p.slug)+'"></div>';
}
async function publish(slug){
  var el=document.getElementById('row-'+slug); if(el) el.style.opacity=.5;
  try { await api('POST','/me/pages/'+slug+'/publish'); } catch(e){ alert(e.message); }
  loadPages();
}
async function unpublish(slug){
  if(!confirm('Take this page offline (back to draft)? It won\'t appear publicly until you publish again.')) return;
  await api('POST','/me/pages/'+slug+'/unpublish'); loadPages();
}
window.publish = publish; window.unpublish = unpublish;

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
  var st=document.getElementById('genstatus');
  var title = document.getElementById('ptitle').value.trim();
  var body = { title: title||undefined }, localVideoURL = null;
  if(GENTAB==='upload'){
    var f = document.getElementById('file').files[0];
    if(!f){ st.textContent='Choose a video file first.'; return; }
    localVideoURL = URL.createObjectURL(f);
    startAnalyzer(localVideoURL); setAzLabel('Uploading your video…');
    try {
      var pre = await api('POST','/me/uploads/presign',{filename:f.name, contentType:f.type||'video/mp4'});
      var put = await fetch(pre.uploadUrl, {method:'PUT', headers:{'Content-Type':f.type||'video/mp4'}, body:f});
      if(!put.ok){ throw new Error('Upload failed ('+put.status+')'); }
      body.uploadKey = pre.key;
    } catch(e){ azError(e.message); return; }
  } else {
    var url = document.getElementById('url').value.trim();
    if(!url){ st.textContent='Paste a video link first.'; return; }
    body.url = url; startAnalyzer(null);
  }
  setAzLabel('Starting…');
  try {
    var r = await api('POST','/me/generate',body);
    if(r.status==='received'){ azDone(null, true); return; }
    await pollAnalyze(r.jobId);
  } catch(e){ azError(e.message); }
}

// --- live analysis view ----------------------------------------------------
var AZ = { revealed: 0 };
function fmtT(t){ t=Math.max(0,Math.round(t||0)); return Math.floor(t/60)+':'+('0'+(t%60)).slice(-2); }

var LOCAL_VIDEO_URL = null;
function startAnalyzer(videoURL){
  AZ = { revealed: 0 };
  LOCAL_VIDEO_URL = videoURL || null;
  app.innerHTML =
   '<div class="az">'+
     '<div class="az-head"><div class="az-dotwrap"><span class="az-dot"></span></div>'+
       '<h1 id="az-label" style="margin:6px 0 2px">Analyzing your video</h1>'+
       '<div class="az-sub" id="az-sub">Watching every second to find the products…</div></div>'+
     '<div class="az-body">'+
       '<div class="az-stage" id="az-stage">'+
         (videoURL ? '<video id="az-vid" class="az-vid" muted playsinline loop autoplay src="'+videoURL+'"></video>'
                   : '<div class="az-vid az-ph">🎬</div>')+
         '<div class="az-scan"></div><div class="az-grid"></div>'+
       '</div>'+
       '<div class="az-panel">'+
         '<div class="az-count" id="az-count"><span class="spin"></span> Looking for products…</div>'+
         '<div class="az-list" id="az-list"></div>'+
       '</div>'+
     '</div>'+
     '<div class="az-foot" id="az-foot"></div>'+
   '</div>';
  var v=document.getElementById('az-vid'); if(v&&v.play){ v.play().catch(function(){}); }
}
function setAzLabel(t){ var e=document.getElementById('az-label'); if(e) e.textContent=t; }
function setAzSub(t){ var e=document.getElementById('az-sub'); if(e) e.textContent=t||''; }
function pingStage(){ var s=document.getElementById('az-stage'); if(!s)return; s.classList.remove('ping'); void s.offsetWidth; s.classList.add('ping'); }

function revealNext(preview){
  if(AZ.revealed >= preview.length) return false;
  var p = preview[AZ.revealed++];
  var v=document.getElementById('az-vid');
  if(v && p.t){ try{ v.currentTime = p.t; }catch(e){} }
  pingStage();
  var list=document.getElementById('az-list');
  if(list){
    var label=((p.brand||'')+' '+(p.name||'')).trim() || 'Product';
    var card=document.createElement('div'); card.className='az-item';
    card.innerHTML='<div class="az-em">🔎</div><div class="az-tx"><div class="az-nm">'+esc(label)+
      (p.variant?' <span class="az-var">'+esc(p.variant)+'</span>':'')+'</div>'+
      '<div class="az-ts">found at '+fmtT(p.t)+'</div></div>';
    list.insertBefore(card, list.firstChild);
    requestAnimationFrame(function(){ card.classList.add('in'); });
  }
  var c=document.getElementById('az-count'); if(c) c.textContent = AZ.revealed+' product'+(AZ.revealed!==1?'s':'')+' found';
  return true;
}

async function pollAnalyze(job){
  var preview=[], revealTimer=null, ambient=null, ai=0, lastPhase='';
  var AMBIENT=['Listening to the audio…','Scanning the footage…','Reading on-screen text…','Matching products…'];
  function stop(){ if(revealTimer){clearInterval(revealTimer);revealTimer=null;} if(ambient){clearInterval(ambient);ambient=null;} }
  for(var i=0;i<400;i++){
    await new Promise(function(res){setTimeout(res,2500);});
    var s; try { s = await api('GET','/me/generate/'+job); } catch(e){ continue; }
    if(s.phase==='analyzing' && lastPhase!=='analyzing'){
      setAzLabel('Analyzing your video');
      if(!ambient) ambient=setInterval(function(){ setAzSub(AMBIENT[ai++ % AMBIENT.length]); }, 2100);
    }
    if(!preview.length && s.preview && s.preview.length){
      preview = s.preview;
      if(ambient){ clearInterval(ambient); ambient=null; } setAzSub('Products detected in the video ✨');
      if(!revealTimer) revealTimer=setInterval(function(){ if(!revealNext(preview)){ clearInterval(revealTimer); revealTimer=null; } }, 800);
    }
    if(s.phase==='building') setAzLabel('Pricing & building your page');
    lastPhase = s.phase || lastPhase;
    if(s.status==='done'){ stop(); while(revealNext(preview)){}
      if(s.pageSlug){ setTimeout(function(){ showProductReview(s.pageSlug); }, 650); }
      else { azDone(null, false); } return; }
    if(s.status==='error'){ stop(); azError(s.error||'Something went wrong'); return; }
  }
}

function azDone(slug, received){
  var v=document.getElementById('az-vid'); if(v){ try{ v.currentTime=0; v.play(); }catch(e){} }
  var sc=document.querySelector('.az-scan'); if(sc) sc.style.display='none';
  setAzLabel(received?'Got it — we\'re building your page':'✓ Draft ready to review');
  setAzSub(received?'We\'ll email you when it\'s live.':'Check it over, edit anything, then approve to go live.');
  var c=document.getElementById('az-count'); if(c && AZ.revealed) c.textContent = AZ.revealed+' product'+(AZ.revealed!==1?'s':'')+' found';
  var foot=document.getElementById('az-foot');
  if(foot){
    foot.innerHTML = received
      ? '<button class="btn" onclick="viewDashboard()">Back to your pages</button>'
      : '<button class="btn" onclick="viewDashboard()">Review &amp; publish →</button>'+
        (slug?' <a class="btn ghost" href="{{BASE}}/'+esc(me.handle)+'/'+esc(slug)+'" target="_blank">Preview draft</a>':'');
  }
}
function azError(msg){
  var sc=document.querySelector('.az-scan'); if(sc) sc.style.display='none';
  setAzLabel('That didn\'t work'); setAzSub('');
  var foot=document.getElementById('az-foot');
  if(foot) foot.innerHTML='<div class="err" style="margin-bottom:14px">'+esc(msg)+'</div><button class="btn ghost" onclick="viewDashboard()">← Back &amp; try again</button>';
}
window.viewDashboard = viewDashboard;

// --- post-analysis: review + edit products, then publish -------------------
var REVIEW = { slug:null, page:null };

async function showProductReview(slug){
  REVIEW.slug = slug;
  var page; try { page = await api('GET','/me/pages/'+slug); } catch(e){ azError(e.message); return; }
  REVIEW.page = page;
  var vid = LOCAL_VIDEO_URL
    ? '<video class="rv-vid" src="'+LOCAL_VIDEO_URL+'" muted playsinline loop autoplay></video>'
    : '<div class="rv-vid rv-vidph">🎬</div>';
  app.innerHTML =
    '<div class="rv2">'+
    '<div class="rv-head"><h1>Found '+page.products.length+' product'+(page.products.length!==1?'s':'')+' ✨</h1>'+
      '<p class="sub">Check each one’s brand, name and link. Add anything we missed — then publish.</p></div>'+
    '<div class="rv-split">'+
      '<div class="rv-videocol">'+vid+'</div>'+
      '<div class="rv-editcol">'+
        '<div id="rv-list"></div>'+
        '<button class="btn ghost sm" id="rv-add" style="margin-top:4px">+ Add a product</button>'+
        '<div class="rv-actions">'+
          '<button class="btn" id="rv-pub">Auto Publish</button>'+
          '<button class="btn ink" id="rv-edit">Edit &amp; Review your page</button>'+
        '</div>'+
        '<div class="muted" id="rv-status" style="margin-top:12px"></div>'+
      '</div>'+
    '</div></div>';
  var v=document.querySelector('.rv-vid'); if(v&&v.play){ v.play().catch(function(){}); }
  renderReviewProducts();
  document.getElementById('rv-add').onclick = addReviewProduct;
  document.getElementById('rv-pub').onclick = autoPublish;
  document.getElementById('rv-edit').onclick = editAndReview;
}
window.showProductReview = showProductReview;

function renderReviewProducts(){
  document.getElementById('rv-list').innerHTML = REVIEW.page.products.map(productCard).join('');
}
function productCard(p){
  var title = ((p.brand||'')+' '+(p.name||'')).trim() || 'New product';
  var link = (p.linkKind==='own') ? (p.url||'') : '';
  return '<details class="rv-prod" data-id="'+esc(p.id||'')+'">'+
    '<summary><span class="rv-em">'+esc(p.emoji||'🛍️')+'</span>'+
      '<span class="rv-t">'+esc(title)+'</span><span class="rv-chev">▾</span></summary>'+
    '<div class="rv-fields">'+
      '<label>Brand</label><input class="rv-brand" value="'+esc(p.brand||'')+'" oninput="rvSyncTitle(this)">'+
      '<label>Product name</label><input class="rv-name" value="'+esc(p.name||'')+'" oninput="rvSyncTitle(this)">'+
      '<label>Affiliate link <span class="muted">(your own — optional)</span></label>'+
      '<input class="rv-url" type="url" placeholder="https://…" value="'+esc(link)+'">'+
      '<div style="margin-top:10px"><button class="btn danger sm" onclick="removeReviewProduct(this)">Remove</button></div>'+
    '</div></details>';
}
function rvSyncTitle(inp){
  var card=inp.closest('.rv-prod');
  var t=(card.querySelector('.rv-brand').value+' '+card.querySelector('.rv-name').value).trim();
  card.querySelector('.rv-t').textContent = t || 'New product';
}
window.rvSyncTitle = rvSyncTitle;
function addReviewProduct(){
  var box=document.getElementById('rv-list');
  var d=document.createElement('div'); d.innerHTML=productCard({emoji:'🆕'});
  var card=d.firstChild; box.appendChild(card); card.open=true;
  card.querySelector('.rv-brand').focus();
}
function removeReviewProduct(btn){
  var card=btn.closest('.rv-prod');
  if(card.getAttribute('data-id')){ card.setAttribute('data-remove','1'); card.style.display='none'; }
  else { card.remove(); }
}
window.removeReviewProduct = removeReviewProduct;
function collectProducts(){
  var out=[];
  document.querySelectorAll('.rv-prod').forEach(function(c){
    var id=c.getAttribute('data-id');
    if(c.getAttribute('data-remove')==='1'){ if(id) out.push({id:id, remove:true}); return; }
    var brand=c.querySelector('.rv-brand').value.trim();
    var name=c.querySelector('.rv-name').value.trim();
    var url=c.querySelector('.rv-url').value.trim();
    if(!id && !brand && !name) return;
    var e={ brand:brand, name:name, url:url };
    if(id) e.id=id;
    out.push(e);
  });
  return out;
}
async function autoPublish(){
  var st=document.getElementById('rv-status'); st.innerHTML='<span class="spin"></span> Publishing…';
  try {
    await api('PATCH','/me/pages/'+REVIEW.slug, { products: collectProducts() });
    await api('POST','/me/pages/'+REVIEW.slug+'/publish');
    showPublished(REVIEW.slug);
  } catch(e){ st.innerHTML='<span class="err">'+esc(e.message)+'</span>'; }
}
async function editAndReview(){
  var st=document.getElementById('rv-status'); st.innerHTML='<span class="spin"></span> Saving…';
  try { await api('PATCH','/me/pages/'+REVIEW.slug, { products: collectProducts() }); }
  catch(e){ st.innerHTML='<span class="err">'+esc(e.message)+'</span>'; return; }
  showPageEditor(REVIEW.slug);
}

function showPublished(slug){
  app.innerHTML='<div class="rv" style="text-align:center">'+
    '<div style="font-size:52px">🎉</div><h1>You’re live</h1>'+
    '<p class="sub">Your routine page is published.</p>'+
    '<div class="rv-actions" style="justify-content:center">'+
    '<a class="btn" href="{{BASE}}/'+esc(me.handle)+'/'+esc(slug)+'" target="_blank">View live page →</a>'+
    '<button class="btn ink" onclick="viewDashboard()">Your pages</button></div></div>';
}
window.showPublished = showPublished;

// --- "Edit & Review your page": the REAL page, editable inline (iframe) -----
var EDIT_PAGE = null;
async function showPageEditor(slug){
  var p; try { p = await api('GET','/me/pages/'+slug); } catch(e){ alert(e.message); return; }
  EDIT_PAGE = p;
  app.innerHTML =
    '<div class="ed-bar">'+
      '<button class="btn ghost sm" onclick="backToReview()">← Back</button>'+
      '<div class="ed-hint">Tap any <span class="ed-chip">highlighted</span> text to edit it. Add your own Q&amp;A at the bottom.</div>'+
      '<span class="muted" id="ed-status"></span>'+
      '<button class="btn sm" id="ed-pub">Save &amp; Publish</button>'+
    '</div>'+
    '<iframe id="ed-frame" class="ed-frame" src="{{BASE}}/'+esc(p.handle)+'/'+esc(p.slug)+'?e=1"></iframe>';
  var fr=document.getElementById('ed-frame');
  fr.onload=function(){ try{ initEditFrame(fr); }catch(e){ console.log(e); } };
  document.getElementById('ed-pub').onclick=savePublish;
}
window.showPageEditor = showPageEditor;
// Open the editable page from the dashboard (Back returns to the pages list).
function editFromDash(slug){ REVIEW.slug = null; showPageEditor(slug); }
window.editFromDash = editFromDash;
function backToReview(){ if(REVIEW.slug){ showProductReview(REVIEW.slug); } else { viewDashboard(); } }
window.backToReview = backToReview;

function initEditFrame(fr){
  var doc = fr.contentDocument || fr.contentWindow.document;
  var st=doc.createElement('style');
  st.textContent =
    '[data-edit]{outline:2px dashed rgba(111,93,240,.5);outline-offset:3px;border-radius:5px;cursor:text}'+
    '[data-edit]:hover{background:rgba(111,93,240,.07)}'+
    '[data-edit]:focus{background:rgba(111,93,240,.10);outline-style:solid;outline-color:#6F5DF0}'+
    '.ed-addfaq{display:inline-flex;gap:6px;margin-top:16px;padding:10px 16px;border:1.5px dashed #6F5DF0;'+
      'border-radius:999px;color:#5A47E0;font-weight:600;cursor:pointer;background:#fff;font-family:inherit}'+
    '[data-custom] summary{cursor:text}';
  doc.head.appendChild(st);
  doc.querySelectorAll('[data-edit],[data-cq],[data-ca]').forEach(function(el){
    el.setAttribute('contenteditable','true'); el.spellcheck=false;
  });
  // Editing only — neutralise navigation + the page's own JS buttons.
  doc.querySelectorAll('a,button').forEach(function(el){
    el.addEventListener('click', function(e){ e.preventDefault(); e.stopPropagation(); }, true);
  });
  var list=doc.querySelector('.faq-list');
  if(list){
    var add=doc.createElement('button'); add.type='button'; add.className='ed-addfaq';
    add.textContent='+ Add your own question';
    add.addEventListener('click', function(){ addFrameFaq(doc, list); });
    list.parentNode.insertBefore(add, list.nextSibling);
  }
}
function addFrameFaq(doc, list){
  var d=doc.createElement('details'); d.className='faq-item'; d.setAttribute('data-custom','1'); d.open=true;
  d.innerHTML='<summary data-cq contenteditable="true">Your question?</summary>'+
              '<div class="faq-a" data-ca contenteditable="true">Your answer.</div>';
  list.appendChild(d);
  var s=d.querySelector('summary'); s.focus();
}
async function savePublish(){
  var fr=document.getElementById('ed-frame'); var doc=fr.contentDocument||fr.contentWindow.document;
  var st=document.getElementById('ed-status'); st.innerHTML='<span class="spin"></span> Publishing…';
  var txt=function(el){ return el ? (el.textContent||'').trim() : undefined; };
  var one=function(sel){ return txt(doc.querySelector(sel)); };
  var posId={}; (EDIT_PAGE.products||[]).forEach(function(p){ posId[String(p.position)]=p.id; });
  var products=[];
  doc.querySelectorAll('.s-product[data-pos]').forEach(function(el){
    var id=posId[el.getAttribute('data-pos')]; if(!id) return;
    products.push({ id:id,
      brand: txt(el.querySelector('[data-edit=\"brand\"]')),
      name:  txt(el.querySelector('[data-edit=\"name\"]')),
      note:  txt(el.querySelector('[data-edit=\"note\"]')) });
  });
  var customFaqs=[];
  doc.querySelectorAll('[data-custom=\"1\"]').forEach(function(f){
    var q=txt(f.querySelector('[data-cq]')); var a=txt(f.querySelector('[data-ca]'));
    if(q && q!=='Your question?') customFaqs.push({ q:q, a:(a==='Your answer.'?'':a) });
  });
  var body={ title:one('[data-edit=\"title\"]'), intro:one('[data-edit=\"intro\"]'),
             disclosure:one('[data-edit=\"disclosure\"]'), products:products, customFaqs:customFaqs };
  try {
    await api('PATCH','/me/pages/'+EDIT_PAGE.slug, body);
    await api('POST','/me/pages/'+EDIT_PAGE.slug+'/publish');
    showPublished(EDIT_PAGE.slug);
  } catch(e){ st.innerHTML='<span class="err">'+esc(e.message)+'</span>'; }
}
window.savePublish = savePublish;

function showFatal(msg){
  app.innerHTML = '<h1>Almost there</h1><div class="card" style="max-width:500px">'+
    '<p class="err">'+esc(msg)+'</p><div style="height:12px"></div>'+
    '<button class="btn ghost sm" onclick="signOut()">Sign out &amp; retry</button></div>';
}
async function render(){
  await authConfig();
  header();
  if(AUTHCFG.provider==='supabase'){
    var c = await supa();
    var sess = (await c.auth.getSession()).data.session;   // picks up OAuth/magic-link redirect too
    tok = sess ? sess.access_token : '';
    if(tok) localStorage.setItem('reelie.token', tok);
  }
  if(!tok){ (AUTHCFG.provider==='supabase' ? viewSupabaseLogin() : viewLogin()); return; }
  // Verify with the backend explicitly so a rejection is VISIBLE (not a silent bounce).
  var r;
  try { r = await fetch(BASE+'/me', {headers:{'Authorization':'Bearer '+tok}}); }
  catch(e){ showFatal('Network error reaching the server: '+e.message); return; }
  if(r.status===401){ showFatal('Signed in with Supabase, but the server rejected the session (401 from /me). This is the backend token verification.'); return; }
  if(!r.ok){ showFatal('Server returned '+r.status+' from /me.'); return; }
  me = await r.json(); localStorage.setItem('reelie.user', JSON.stringify(me));
  header();
  var isCreator = (me.role==='creator' || me.role==='both') && me.handle;
  if(!isCreator){ viewApply(); }
  else if(me.approved){ viewDashboard(); }
  else { viewPending(); }
}
window.render = render;
render();
</script>
</body></html>"""
