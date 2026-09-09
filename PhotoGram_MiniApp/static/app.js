const tg=window.Telegram?.WebApp; if(tg){tg.ready();tg.expand();}
let me=null, backAction=null, currentChatUser=null, chatTimer=null;

async function api(url,opt={}){let r=await fetch(url,opt);let d=await r.json();if(!r.ok)throw new Error(d.error||"Xatolik");return d}
function esc(s=""){return String(s).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}
function avatar(u){return u.photo_url?`<img class="avatar" src="${esc(u.photo_url)}">`:`<div class="avatar" style="display:grid;place-items:center">${esc((u.first_name||"?")[0])}</div>`}

function setBack(fn){
 backAction=fn||null;
 if(tg?.BackButton){backAction?tg.BackButton.show():tg.BackButton.hide();}
}
if(tg?.BackButton)tg.BackButton.onClick(()=>{if(backAction)backAction();else closeModal()});

async function login(){
 let u=tg?.initDataUnsafe?.user;
 if(!u){document.body.insertAdjacentHTML("afterbegin",'<div style="padding:10px;background:#7a4b22">Bu Mini App Telegram ichida ochilganda avtomatik login ishlaydi. Brauzer testi uchun demo Telegram ID yuboriladi.</div>');u={id:localStorage.demoId||(localStorage.demoId=Math.floor(Math.random()*9e8+1e8)),first_name:"Demo User",username:"demo"}}
 let d=await api("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({telegram_id:u.id,first_name:u.first_name,username:u.username,photo_url:u.photo_url})});me=d.user;
}

async function loadFeed(){
 stopChatRefresh();setBack(null);
 let d=await api("/api/feed");let f=document.querySelector("#feed");f.style.display="";
 f.innerHTML=d.posts.length?d.posts.map(p=>`<article class="card"><div class="userrow" onclick="openProfile(${p.user.id})">${avatar(p.user)}<b>${esc(p.user.first_name)} ${p.user.verified?"✓":""}</b><span style="color:#aaa">@${esc(p.user.username||"user")}</span></div><img class="photo" src="${esc(p.image)}"><div class="actions"><button onclick="like(${p.id},this)">${p.liked?"❤️":"🤍"} <span>${p.likes}</span></button><button onclick="openComments(${p.id})">💬 ${p.comments}</button><button onclick="reportPost(${p.id})">🚩</button>${p.is_owner||me?.is_admin?`<button class="danger" onclick="deletePost(${p.id})">🗑</button>`:""}</div>${p.caption?`<div class="caption">${esc(p.caption)}</div>`:""}<div class="meta">${new Date(p.created_at).toLocaleString()}</div></article>`).join(""):"<p style='padding:30px;text-align:center'>Hali post yo'q. Birinchi bo'lib rasm joylang 📸</p>";
}

async function like(id,b){let d=await api(`/api/posts/${id}/like`,{method:"POST"});b.innerHTML=`${d.liked?"❤️":"🤍"} <span>${d.likes}</span>`}
function modal(html){document.querySelector("#sheet").innerHTML=html;document.querySelector("#modal").classList.remove("hidden")}
function closeModal(){stopChatRefresh();document.querySelector("#modal").classList.add("hidden");setBack(null)}

function openUpload(){setBack(closeModal);modal(`<h2>📸 Yangi post</h2><form id="uploadForm"><input type="file" name="image" accept="image/*" required><textarea name="caption" placeholder="Rasm haqida yozing..."></textarea><button class="primary">Joylash</button> <button type="button" onclick="closeModal()">Bekor</button></form>`);document.querySelector("#uploadForm").onsubmit=async e=>{e.preventDefault();try{let r=await fetch("/api/posts",{method:"POST",body:new FormData(e.target)});let d=await r.json();if(!r.ok)throw Error(d.error);closeModal();loadFeed()}catch(x){alert(x.message)}}}

async function openComments(id){
 setBack(closeModal);let d=await api(`/api/posts/${id}/comments`);
 modal(`<button class="back-in-app" onclick="closeModal()">← Orqaga</button><h2>💬 Kommentlar</h2><div id="comments">${d.comments.map(c=>`<div class="comment"><b>${esc(c.user.first_name)}</b><br>${esc(c.text)}</div>`).join("")||"Hali komment yo'q"}</div><form id="commentForm"><textarea id="ct" placeholder="Komment yozing..." required></textarea><button class="primary">Yuborish</button></form>`);
 document.querySelector("#commentForm").onsubmit=async e=>{e.preventDefault();await api(`/api/posts/${id}/comments`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text:document.querySelector("#ct").value})});openComments(id)}
}

async function openProfile(id){
 let d=await api(`/api/users/${id}`);let u=d.user;setBack(closeModal);
 modal(`<button class="back-in-app" onclick="closeModal()">← Orqaga</button><div style="text-align:center">${avatar(u)}<h2>${esc(u.first_name)} ${u.verified?"✓":""}</h2><p>@${esc(u.username||"user")}</p><p>${esc(u.bio||"")}</p><p><b>${u.posts}</b> posts · <b>${u.followers}</b> followers · <b>${u.following}</b> following</p>${me&&me.id!==u.id?`<button class="primary" onclick="toggleFollow(${u.id})">${d.followed?"Unfollow":"Follow"}</button> <button class="primary" onclick="openChat(${u.id})">💬 Xabar</button>`:""}<div class="grid">${d.posts.map(p=>`<img src="${esc(p.image)}">`).join("")}</div></div>`)
}
async function toggleFollow(id){await api(`/api/users/${id}/follow`,{method:"POST"});openProfile(id)}
async function openMe(){if(!me)return;let d=await api(`/api/users/${me.id}`);setBack(closeModal);modal(`<button class="back-in-app" onclick="closeModal()">← Orqaga</button><h2>👤 Profil</h2>${avatar(d.user)}<h3>${esc(d.user.first_name)}</h3><textarea id="bio">${esc(d.user.bio||"")}</textarea><button class="primary" onclick="saveBio()">Saqlash</button>${me.is_admin?'<a href="/admin" style="margin-left:8px">👑 Admin panel</a>':""}<div class="grid">${d.posts.map(p=>`<img src="${esc(p.image)}">`).join("")}</div>`)}
async function saveBio(){let d=await api("/api/profile",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({bio:document.querySelector("#bio").value})});me=d.user;alert("Saqlandi")}
async function deletePost(id){if(confirm("Post o'chirilsinmi?")){await api(`/api/posts/${id}`,{method:"DELETE"});loadFeed()}}
async function reportPost(id){let reason=prompt("Shikoyat sababi:");if(reason){await api(`/api/posts/${id}/report`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reason})});alert("Shikoyat yuborildi")}}

function stopChatRefresh(){if(chatTimer){clearInterval(chatTimer);chatTimer=null}currentChatUser=null}
async function openMessages(){
 stopChatRefresh();setBack(loadFeed);let d=await api("/api/conversations");
 modal(`<button class="back-in-app" onclick="closeModal();loadFeed()">← Orqaga</button><h2>💬 Xabarlar</h2><input id="userSearch" placeholder="Foydalanuvchi qidirish..." oninput="searchUsers(this.value)"><div id="userResults"></div><div id="conversationList">${d.conversations.length?d.conversations.map(c=>`<div class="chat-row" onclick="openChat(${c.user.id})">${avatar(c.user)}<div><b>${esc(c.user.first_name)}</b><br><small>${esc(c.last_message)}</small></div>${c.unread?`<span class="unread">${c.unread}</span>`:""}</div>`).join(""):"<p>Hali chatlar yo'q. Foydalanuvchini qidirib yozishni boshlang.</p>"}</div>`);
}
async function searchUsers(q){
 let box=document.querySelector("#userResults");if(!box)return;
 if(!q.trim()){box.innerHTML="";return}
 let d=await api("/api/users/search?q="+encodeURIComponent(q));
 box.innerHTML=d.users.map(u=>`<div class="chat-row" onclick="openChat(${u.id})">${avatar(u)}<div><b>${esc(u.first_name)}</b><br><small>@${esc(u.username||"user")}</small></div></div>`).join("")||"<p>Topilmadi</p>";
}
async function openChat(uid){
 let d=await api(`/api/messages/${uid}`);currentChatUser=uid;setBack(openMessages);
 renderChat(d);
 if(chatTimer)clearInterval(chatTimer);
 chatTimer=setInterval(async()=>{if(currentChatUser===uid){try{let x=await api(`/api/messages/${uid}`);renderChat(x,true)}catch(e){}}},4000);
}
function renderChat(d,keep=false){
 let oldScroll=document.querySelector("#chatMessages")?.scrollTop;
 modal(`<div class="chat-head"><button class="back-in-app" onclick="openMessages()">←</button>${avatar(d.user)}<b>${esc(d.user.first_name)}</b></div><div id="chatMessages" class="chat-messages">${d.messages.map(m=>`<div class="bubble ${m.sender_id===me.id?"mine":"theirs"}">${esc(m.text)}<small>${new Date(m.created_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</small></div>`).join("")}</div><form id="messageForm" class="message-form"><input id="messageText" maxlength="2000" placeholder="Xabar yozing..." autocomplete="off"><button class="primary">Yuborish</button></form>`);
 let cm=document.querySelector("#chatMessages");cm.scrollTop=cm.scrollHeight;
 document.querySelector("#messageForm").onsubmit=async e=>{e.preventDefault();let inp=document.querySelector("#messageText"),text=inp.value.trim();if(!text)return;inp.value="";await api(`/api/messages/${currentChatUser}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})});let x=await api(`/api/messages/${currentChatUser}`);renderChat(x)}
}

(async()=>{try{await login();let a=await api("/api/admin/announcement");if(a.text)document.querySelector("#announcement").textContent="📢 "+a.text;loadFeed()}catch(e){alert(e.message)}})();