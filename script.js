let code="",playerId="",hostId="",host=false,timer;

const $=id=>document.getElementById(id);
const safe=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
async function post(url,body){let r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});let d=await r.json();if(!r.ok)throw Error(d.error||"შეცდომა");return d}
function show(id){$(id).classList.remove("hidden")}function hide(id){$(id).classList.add("hidden")}
function error(e){$("error").textContent=e.message||e}
function home(){clearInterval(timer);hide("game");hide("join");show("home")}
function showJoin(){hide("home");show("join");$("joinName").value=$("name").value}

async function createGame(){try{let d=await post("/api/create",{name:$("name").value});code=d.code;hostId=d.host_id;host=true;enter()}catch(e){error(e)}}
async function joinGame(){try{let d=await post("/api/join",{code:$("joinCode").value,name:$("joinName").value});code=d.code;playerId=d.player_id;host=false;enter()}catch(e){error(e)}}
function enter(){hide("home");hide("join");show("game");$("code").textContent=code;show(host?"hostPanel":"playerPanel");hide(host?"playerPanel":"hostPanel");timer=setInterval(load,500);load()}
async function load(){try{let r=await fetch("/api/state?code="+encodeURIComponent(code));let s=await r.json();if(!r.ok)throw Error(s.error);render(s)}catch(e){error(e)}}

function render(s){
$("round").textContent=s.round;
let map={};s.players.forEach(p=>map[p.id]=p);
let sorted=[...s.players].sort((a,b)=>b.score-a.score);
$("leaderboard").innerHTML=sorted.length?sorted.map((p,i)=>`<div class="row"><span>${i+1}. ${safe(p.name)}</span><b>${p.score}</b></div>`).join(""):"ჯერ არავინ არის";
if(!host){let r=s.rank_map[playerId];$("rank").textContent=r?`შენი ადგილი ამ რაუნდში: ${r}`:"დაჭირე BUZZ-ს!";$("buzz").disabled=!!r}
if(host){
$("order").innerHTML=s.order.length?s.order.map((id,i)=>`<div class="row"><span>${i+1}. ${safe(map[id]?.name||"")}</span><b>დაჭერა</b></div>`).join(""):"ჯერ არავის დაუჭერია";
$("scores").innerHTML=s.players.map(p=>`<div class="row"><span>${safe(p.name)}</span><span><input class="score" type="number" id="s_${p.id}" value="${p.score}"><button onclick="saveScore('${p.id}')">შენახვა</button></span></div>`).join("")
}}

async function buzz(){try{$("buzz").disabled=true;await post("/api/buzz",{code,player_id:playerId});load()}catch(e){$("buzz").disabled=false;error(e)}}
async function nextRound(){try{await post("/api/next-round",{code,host_id:hostId});load()}catch(e){error(e)}}
async function saveScore(id){try{await post("/api/set-score",{code,host_id:hostId,player_id:id,score:Number($("s_"+id).value)});load()}catch(e){error(e)}}
async function resetScores(){if(!confirm("ყველა ქულა განულდეს?"))return;try{await post("/api/reset-leaderboard",{code,host_id:hostId});load()}catch(e){error(e)}}
