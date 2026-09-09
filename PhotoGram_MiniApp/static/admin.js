const tg=window.Telegram?.WebApp;if(tg){tg.ready();tg.expand();}
async function api(u,o={}){let r=await fetch(u,o),d=await r.json();if(!r.ok)throw Error(d.error||"Xatolik");return d}
const esc=s=>(s||"").replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));
async function login(){let u=tg?.initDataUnsafe?.user||{id:localStorage.demoId,first_name:"Demo Admin"};if(!u?.id)throw Error("Admin panel Telegram orqali ochilishi kerak.");await api("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({telegram_id:u.id,first_name:u.first_name,username:u.username})})}
async function load(){
 let [s,users,posts,reports,a]=await Promise.all([api("/api/admin/stats"),api("/api/admin/users"),api("/api/admin/posts"),api("/api/admin/reports"),api("/api/admin/announcement")]);
 document.querySelector("#admin").innerHTML=`<section class="stats"><div class="stat">${s.users}<small>Users</small></div><div class="stat">${s.posts}<small>Posts</small></div><div class="stat">${s.comments}<small>Comments</small></div><div class="stat">${s.reports}<small>Reports</small></div></section>
 <section class="admin-section"><h2>📢 Announcement</h2><textarea id="ann">${esc(a.text)}</textarea><button class="primary" onclick="saveAnn()">Saqlash</button></section>
 <section class="admin-section"><h2>🚨 Reports (${reports.reports.length})</h2>${reports.reports.map(r=>`<div class="admin-row">Post #${r.post_id}<br>${esc(r.reason)}<br><button onclick="resolve(${r.id})">Hal qilindi</button></div>`).join("")||"Yo'q"}</section>
 <section class="admin-section"><h2>👥 Users</h2>${users.users.map(u=>`<div class="admin-row"><b>${esc(u.first_name)}</b> @${esc(u.username||"")} ${u.verified?"✓":""}<br><small>ID: ${u.telegram_id}</small><br><button onclick="act('/api/admin/users/${u.id}/ban')">${u.banned?"Unban":"Ban"}</button> <button onclick="act('/api/admin/users/${u.id}/verify')">${u.verified?"Unverify":"Verify"}</button></div>`).join("")}</section>
 <section class="admin-section"><h2>📸 Posts</h2>${posts.posts.map(p=>`<div class="admin-row"><img src="${p.image}"><b>${esc(p.user.first_name)}</b><br>${esc(p.caption)}<br><button onclick="act('/api/admin/posts/${p.id}/hide')">${p.hidden?"Show":"Hide"}</button> <button onclick="act('/api/admin/posts/${p.id}/pin')">${p.pinned?"Unpin":"Pin"}</button> <button class="danger" onclick="del(${p.id})">Delete</button></div>`).join("")}</section>`;
}
async function act(u){await api(u,{method:"POST"});load()}
async function resolve(id){await api(`/api/admin/reports/${id}/resolve`,{method:"POST"});load()}
async function del(id){if(confirm("O'chirilsinmi?")){await api(`/api/posts/${id}`,{method:"DELETE"});load()}}
async function saveAnn(){await api("/api/admin/announcement",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text:document.querySelector("#ann").value})});alert("Saqlandi")}
(async()=>{try{await login();await load()}catch(e){document.querySelector("#admin").innerHTML="<h2 style='padding:20px'>"+e.message+"</h2>"}})();
