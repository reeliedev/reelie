"""The closed-beta review console (/admin) — a small token-gated page to approve
or reject creator applications."""

from __future__ import annotations

from app import config


def admin_html() -> str:
    return _ADMIN.replace("{{BRAND}}", config.BRAND)


_ADMIN = r"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{BRAND}} — Beta review</title><meta name="robots" content="noindex">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@0,400;0,500;0,600;0,700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#FFE566;--ink:#201B0A;--grey:#7A6F4A;--line:rgba(32,27,10,.14);--surface:#fff;--accent:#6F5DF0;--green:#2C8C4A;--red:#D64545}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Instrument Sans',-apple-system,sans-serif;color:var(--ink);line-height:1.5;background:radial-gradient(circle at 18% 10%,#FFF3A8 0%,transparent 46%),radial-gradient(circle at 85% 92%,#FFD23E 0%,transparent 52%),var(--bg);min-height:100vh}
.wrap{max-width:820px;margin:0 auto;padding:40px 22px 80px}
h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:32px;letter-spacing:-.5px;margin-bottom:6px}
.sub{color:var(--grey);margin-bottom:24px}
input{width:100%;font:inherit;font-size:15px;padding:13px 15px;border:1px solid var(--line);border-radius:13px;background:#fff;outline:none}
input:focus{border-color:var(--accent);box-shadow:0 0 0 4px rgba(111,93,240,.16)}
.btn{border:none;cursor:pointer;font:inherit;font-weight:700;font-size:14px;padding:10px 16px;border-radius:999px;background:var(--accent);color:#fff}
.btn.sm{padding:8px 14px;font-size:13px}
.btn.ok{background:var(--green)}.btn.no{background:#fff;color:var(--red);border:1.5px solid var(--line)}.btn.danger{background:var(--red);color:#fff}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px 20px;margin-bottom:12px;box-shadow:0 6px 16px rgba(32,27,10,.06)}
.app{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.app .n{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:17px}
.app .m{color:var(--grey);font-size:13px}
.app .links{font-size:13px;margin-top:3px}
.app .links a{color:var(--accent);font-weight:600;border-bottom:2px solid var(--accent);margin-right:12px}
.app .acts{margin-left:auto;display:flex;gap:8px}
.pill{font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;padding:3px 9px;border-radius:999px}
.pill.pending{background:#FFF0C2;color:#8A6D00}.pill.approved{background:#E8F6EC;color:var(--green)}.pill.rejected{background:#F7E4E4;color:var(--red)}
.muted{color:var(--grey)}.err{color:var(--red);margin-top:10px}
.tabs{display:flex;gap:8px;margin-bottom:18px}.tab{padding:7px 14px;border-radius:999px;border:1px solid var(--line);background:#fff;cursor:pointer;font-size:13px;font-weight:600}.tab.on{background:var(--ink);color:#fff;border-color:var(--ink)}
</style></head><body>
<div class="wrap" id="app"><p class="muted">Loading…</p></div>
<script>
var TOK = localStorage.getItem('reelie.admin')||'', app=document.getElementById('app'), FILTER='pending';
function esc(s){ return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
async function api(method, path){
  var r = await fetch(path,{method:method,headers:{'X-Admin-Token':TOK}});
  if(r.status===401){ TOK=''; localStorage.removeItem('reelie.admin'); throw new Error('Bad token'); }
  return r.json();
}
function gate(){
  app.innerHTML='<h1>Beta review</h1><p class="sub">Enter the admin token to review creator applications.</p>'+
    '<div class="card" style="max-width:420px"><input id="t" type="password" placeholder="Admin token">'+
    '<div style="height:12px"></div><button class="btn" id="go">Continue</button><div class="err" id="e" style="display:none"></div></div>';
  document.getElementById('go').onclick=function(){ TOK=document.getElementById('t').value.trim(); localStorage.setItem('reelie.admin',TOK); load(); };
  document.getElementById('t').addEventListener('keydown',function(e){ if(e.key==='Enter') document.getElementById('go').click(); });
}
async function load(){
  if(!TOK){ gate(); return; }
  try {
    var rows = await api('GET','/admin/applications'+(FILTER?'?status='+FILTER:''));
    var reqs = await api('GET','/admin/requests');
    render(rows, reqs);
  } catch(e){ gate(); var el=document.getElementById('e'); if(el){ el.textContent=e.message; el.style.display='block'; } }
}
function tab(name,label){ return '<div class="tab'+(FILTER===name?' on':'')+'" onclick="FILTER=\''+name+'\';load()">'+label+'</div>'; }
function render(rows, reqs){
  var html='';
  // Page-generation requests to build out-of-band during the beta.
  if(reqs && reqs.length){
    html+='<h1>Page requests</h1><p class="sub">'+reqs.length+' link(s) to build. Generate locally, then mark done.</p>';
    reqs.forEach(function(q){
      html+='<div class="card"><div class="app"><div>'+
        '<div class="n">@'+esc(q.handle)+'</div>'+
        '<div class="links"><a href="'+esc(q.url||'#')+'" target="_blank">'+esc(q.url||'(no url)')+'</a></div>'+
        '<div class="m">'+esc((q.at||'').slice(0,16).replace('T',' '))+'</div></div></div></div>';
    });
    html+='<div style="height:24px"></div>';
  }
  html+='<h1>Beta review</h1><p class="sub">Approve creators to let them publish. '+rows.length+' shown.</p>'+
    '<div class="tabs">'+tab('pending','Pending')+tab('approved','Approved')+tab('rejected','Rejected')+tab('','All')+'</div>';
  if(!rows.length){ html+='<p class="muted">Nothing here.</p>'; }
  rows.forEach(function(a){
    var ig=a.instagram?'<a href="https://instagram.com/'+esc(a.instagram)+'" target="_blank">IG @'+esc(a.instagram)+'</a>':'';
    var yt=a.youtube?'<a href="https://youtube.com/@'+esc(a.youtube)+'" target="_blank">YT @'+esc(a.youtube)+'</a>':'';
    html+='<div class="card"><div class="app"><div>'+
      '<div class="n">'+esc(a.displayName||a.handle)+' <span class="pill '+a.status+'">'+a.status+'</span></div>'+
      '<div class="m">@'+esc(a.handle)+' · '+esc(a.email||'no email')+'</div>'+
      '<div class="links">'+ig+yt+(!ig&&!yt?'<span class="muted">no handles submitted</span>':'')+'</div></div>'+
      '<div class="acts">'+
        (a.status!=='approved'?'<button class="btn ok sm" onclick="act(\''+esc(a.handle)+'\',\'approve\')">Approve</button>':'')+
        (a.status!=='rejected'?'<button class="btn no sm" onclick="act(\''+esc(a.handle)+'\',\'reject\')">Reject</button>':'')+
        '<button class="btn danger sm" onclick="removeCreator(\''+esc(a.handle)+'\')">Delete</button>'+
      '</div></div></div>';
  });
  app.innerHTML=html;
}
async function act(handle, what){
  await fetch('/admin/applications/'+handle+'/'+what,{method:'POST',headers:{'X-Admin-Token':TOK}});
  load();
}
async function removeCreator(handle){
  if(!confirm('Permanently delete @'+handle+' and ALL their data (pages, products, sales)?\n\nThis cannot be undone. To free their email for re-signup, also delete them in Supabase → Authentication → Users.')) return;
  await fetch('/admin/applications/'+handle+'/delete',{method:'POST',headers:{'X-Admin-Token':TOK}});
  load();
}
window.act=act; window.removeCreator=removeCreator;
load();
</script></body></html>"""
