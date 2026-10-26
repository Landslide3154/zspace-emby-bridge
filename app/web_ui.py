"""面板页面：单文件 HTML（内联 CSS/JS），离线可用，无构建步骤。"""

ADMIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>极影视进度桥</title>
<link rel="icon" href="/favicon.ico">
<style>
:root{
  --ink:#0B0E14; --surface:#121722; --surface-2:#161C29; --line:#1E2635; --line-soft:#171E2B;
  --fg:#E9EDF5; --dim:#8A94A6; --faint:#5E6879;
  --accent:#5B7CFA; --accent-soft:rgba(91,124,250,.12);
  --ok:#3ED598; --warn:#F2B341; --err:#F0616D;
  --radius:14px;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--ink);color:var(--fg);font:14px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
button{font:inherit;color:inherit;cursor:pointer}
input,select,textarea{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}
.hide{display:none !important}
.topbar{display:flex;align-items:center;gap:12px;padding:14px 26px;border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(11,14,20,.92);backdrop-filter:blur(10px);z-index:20}
.brand{display:flex;align-items:center;gap:10px;min-width:0}
.brand img{width:30px;height:30px;border-radius:8px;display:block}
.brand b{font-weight:650}
.brand span{color:var(--faint);font-size:12px}
.spacer{flex:1}
.pill{display:inline-flex;align-items:center;gap:7px;padding:5px 11px;border:1px solid var(--line);border-radius:999px;font-size:12.5px;color:var(--dim)}
.pill .dot{width:7px;height:7px;border-radius:50%;background:var(--faint)}
.pill.ok .dot{background:var(--ok);box-shadow:0 0 0 4px rgba(62,213,152,.12)}
.pill.warn .dot{background:var(--warn);box-shadow:0 0 0 4px rgba(242,179,65,.12)}
.pill.err .dot{background:var(--err);box-shadow:0 0 0 4px rgba(240,97,109,.12)}
.ghost{background:transparent;border:1px solid var(--line);border-radius:9px;padding:7px 13px;color:var(--dim)}
.ghost:hover{color:var(--fg);border-color:#2C3648}
.shell{display:flex;min-height:calc(100% - 59px)}
.side{width:212px;flex:0 0 212px;border-right:1px solid var(--line);padding:22px 14px;display:flex;flex-direction:column;gap:4px}
.side a{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:9px;color:var(--dim);position:relative;font-size:13.5px}
.side a:hover{background:var(--surface);color:var(--fg)}
.side a[aria-current="page"]{background:var(--accent-soft);color:#CFD8FF}
.side a[aria-current="page"]::before{content:"";position:absolute;left:0;top:9px;bottom:9px;width:2px;border-radius:2px;background:var(--accent)}
.side .svg{width:17px;height:17px;flex:0 0 17px;opacity:.9}
.side .foot{margin-top:auto;padding:12px;color:var(--faint);font-size:12px;line-height:1.5;word-break:break-all}
main{flex:1;min-width:0;padding:30px 32px 130px}
.wrap{max-width:900px;margin:0 auto}
.hero{padding-bottom:20px;border-bottom:1px solid var(--line)}
.hero h1{margin:0;font-size:26px;line-height:1.3;font-weight:650;letter-spacing:-.01em;display:flex;align-items:center;gap:12px}
.hero h1 .dot{width:10px;height:10px;border-radius:50%;background:var(--ok);flex:0 0 10px;animation:pulse 2.4s ease-in-out infinite}
.hero h1.warn .dot{background:var(--warn)} .hero h1.err .dot{background:var(--err)}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(62,213,152,.28)}50%{box-shadow:0 0 0 7px rgba(62,213,152,0)}}
.hero p{margin:8px 0 0;color:var(--dim);font-size:13.5px}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);padding:20px 0 4px}
.metric{padding:2px 20px;border-left:1px solid var(--line)}
.metric:first-child{padding-left:0;border-left:0}
.metric .n{font-family:ui-monospace,SFMono-Regular,"SF Mono",Consolas,monospace;font-size:23px;line-height:1.2;font-variant-numeric:tabular-nums}
.metric .l{color:var(--faint);font-size:12.5px;margin-top:2px}
.metric .n.ok{color:var(--ok)} .metric .n.err{color:var(--err)}
section.block{margin-top:32px}
section.block > h2{font-size:13px;font-weight:600;color:var(--dim);margin:0 0 12px;display:flex;align-items:center;gap:10px}
section.block > h2::after{content:"";flex:1;height:1px;background:var(--line-soft)}
.table-wrap{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:13px}
thead th{text-align:left;font-weight:500;color:var(--faint);padding:10px 14px;background:var(--surface);border-bottom:1px solid var(--line);white-space:nowrap}
tbody td{padding:11px 14px;border-bottom:1px solid var(--line-soft);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:rgba(255,255,255,.015)}
.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Consolas,monospace;font-variant-numeric:tabular-nums;font-size:12.5px;color:#C5CEDF;white-space:nowrap}
.name{color:#DCE3F0}
.sub{color:var(--faint);font-size:12px;margin-top:2px;word-break:break-all}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11.5px;border:1px solid var(--line);color:var(--dim)}
.tag.ok{color:var(--ok);border-color:rgba(62,213,152,.3);background:rgba(62,213,152,.07)}
.tag.warn{color:var(--warn);border-color:rgba(242,179,65,.3);background:rgba(242,179,65,.07)}
.empty{padding:24px 14px;text-align:center;color:var(--faint);font-size:13px}
.live{display:flex;align-items:center;gap:14px;padding:14px 16px;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:10px}
.live .pos{font-family:ui-monospace,Consolas,monospace;color:var(--ok);font-size:15px;white-space:nowrap}
.live .meta{flex:1;min-width:0}
.events{display:flex;flex-direction:column;gap:2px}
.event{display:flex;gap:12px;padding:9px 2px;border-bottom:1px solid var(--line-soft);font-size:13px}
.event:last-child{border-bottom:0}
.event .when{color:var(--faint);font-family:ui-monospace,Consolas,monospace;font-size:12px;white-space:nowrap}
.event .what{color:var(--dim)}
.group{border-top:1px solid var(--line-soft);padding:2px 0 6px}
.group:first-of-type{border-top:0}
.group h3{font-size:12.5px;color:var(--faint);font-weight:500;margin:18px 0 4px}
.field{display:flex;align-items:center;gap:18px;padding:12px 0;border-bottom:1px solid var(--line-soft)}
.field:last-child{border-bottom:0}
.field .meta{flex:1;min-width:0}
.field .name{font-size:13.5px}
.field .hint{color:var(--faint);font-size:12.5px;margin-top:2px}
.field input[type=number],.field input[type=text],.field input[type=url],.field input[type=password],.field select{width:190px;background:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px 10px;text-align:right}
.field input:focus,.field select:focus{border-color:var(--accent)}
.field .wide{width:320px;text-align:left}
.switch{position:relative;width:42px;height:24px;flex:0 0 42px}
.switch input{position:absolute;opacity:0;width:100%;height:100%;margin:0;cursor:pointer}
.switch .track{position:absolute;inset:0;border-radius:999px;background:#232B3B;transition:background .18s}
.switch .knob{position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#9AA5B8;transition:transform .18s,background .18s}
.switch input:checked + .track{background:rgba(91,124,250,.28)}
.switch input:checked + .track + .knob{transform:translateX(18px);background:var(--accent)}
.savedbar{position:fixed;left:0;right:0;bottom:0;display:flex;justify-content:center;pointer-events:none}
.savedbar .inner{pointer-events:auto;margin:0 16px 18px;display:flex;align-items:center;gap:12px;background:var(--surface-2);border:1px solid var(--line);border-radius:12px;padding:10px 12px 10px 16px;box-shadow:0 14px 34px rgba(0,0,0,.45)}
.savedbar .txt{color:var(--dim);font-size:13px}
.primary{background:var(--accent);border:0;color:#fff;border-radius:9px;padding:9px 16px;font-weight:600}
.primary:disabled{opacity:.45;cursor:default}
.danger{background:transparent;border:1px solid rgba(240,97,109,.35);color:var(--err);border-radius:9px;padding:9px 16px}
.tool-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.tool-row input{flex:1;min-width:220px;background:var(--ink);border:1px solid var(--line);border-radius:9px;padding:9px 12px;text-align:left}
pre.out{margin:14px 0 0;padding:14px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:#C5CEDF;font-family:ui-monospace,Consolas,monospace;font-size:12.5px;white-space:pre-wrap;max-height:320px;overflow:auto}
.result{font-size:12.5px;margin-left:10px}
.result.ok{color:var(--ok)} .result.err{color:var(--err)}
.auth{max-width:380px;margin:64px auto;padding:0 24px}
.auth .card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:26px}
.auth img{width:44px;height:44px;border-radius:11px;display:block;margin-bottom:16px}
.auth h1{font-size:19px;margin:0 0 6px;font-weight:650}
.auth p{color:var(--dim);font-size:13px;margin:0 0 20px}
.auth input{width:100%;background:var(--ink);border:1px solid var(--line);border-radius:9px;padding:11px 12px;margin-bottom:12px}
.auth button{width:100%}
.msg{color:var(--err);font-size:12.5px;min-height:18px;margin:8px 0 0}
#toast{position:fixed;left:50%;bottom:26px;transform:translate(-50%,14px);opacity:0;pointer-events:none;background:#1B2230;border:1px solid var(--line);border-radius:10px;padding:10px 16px;font-size:13px;transition:opacity .2s,transform .2s;z-index:40;box-shadow:0 12px 30px rgba(0,0,0,.4)}
#toast.show{opacity:1;transform:translate(-50%,0)}
#toast.err{border-color:rgba(240,97,109,.4);color:#FFD5D8}
@media (prefers-reduced-motion:reduce){*{animation:none !important;transition:none !important}}
@media (max-width:860px){
  .shell{display:block}
  .side{width:auto;flex:none;border-right:0;border-bottom:1px solid var(--line);padding:8px 14px;flex-direction:row;overflow-x:auto;gap:2px}
  .side a{padding:8px 12px;white-space:nowrap}
  .side a[aria-current="page"]::before{display:none}
  .side .foot{display:none}
  main{padding:22px 18px 140px}
  .hero h1{font-size:21px}
  .metrics{grid-template-columns:repeat(2,1fr);row-gap:16px}
  .metric{padding:0 14px}
  .metric:nth-child(odd){border-left:0;padding-left:0}
  .field{flex-wrap:wrap;gap:10px}
  .field input[type=number],.field input[type=text],.field input[type=url],.field input[type=password],.field select,.field .wide{width:100%;text-align:left}
}
</style>
</head>
<body>
<header class="topbar">
  <div class="brand"><img src="/icon.png" alt=""><b>极影视进度桥</b><span id="brandVersion"></span></div>
  <div class="spacer"></div>
  <span class="pill" id="pill"><span class="dot"></span><span id="pillText">连接中</span></span>
  <button class="ghost hide" id="logoutBtn">退出登录</button>
</header>

<div class="auth hide" id="authView">
  <div class="card">
    <img src="/icon.png" alt="">
    <h1 id="authTitle">登录</h1>
    <p id="authHint"></p>
    <input type="password" id="pwd" placeholder="管理密码" autocomplete="current-password">
    <button class="primary" id="authBtn">继续</button>
    <p class="msg" id="authMsg"></p>
  </div>
</div>

<div class="shell hide" id="appView">
  <nav class="side">
    <a href="#overview" data-view="overview" aria-current="page">
      <svg class="svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 13h5l2 4 3-9 2 5h4"/></svg>概览</a>
    <a href="#settings" data-view="settings">
      <svg class="svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3.2"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/></svg>设置</a>
    <a href="#tools" data-view="tools">
      <svg class="svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="6.2"/><path d="M15.5 15.5 20 20"/></svg>工具</a>
    <div class="foot"><div id="sideUpstream"></div><div id="sideMode"></div></div>
  </nav>

  <main>
    <div class="wrap">
      <section id="view-overview">
        <div class="hero">
          <h1 id="stateTitle"><span class="dot"></span>正在读取状态</h1>
          <p id="stateSub">等待第一次心跳</p>
        </div>
        <div class="metrics">
          <div class="metric"><div class="n" id="mRecords">–</div><div class="l">本地记录</div></div>
          <div class="metric"><div class="n" id="mReports">–</div><div class="l">累计上报</div></div>
          <div class="metric"><div class="n ok" id="mWritten">–</div><div class="l">写库成功</div></div>
          <div class="metric"><div class="n" id="mFailed">–</div><div class="l">写库失败</div></div>
        </div>

        <section class="block" id="liveBlock">
          <h2>正在播放</h2>
          <div id="liveList"></div>
        </section>

        <section class="block">
          <h2>最近同步</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>时间</th><th>片名 / 文件</th><th>位置</th><th>状态</th></tr></thead>
              <tbody id="recentBody"></tbody>
            </table>
          </div>
        </section>

        <section class="block">
          <h2>同步事件</h2>
          <div class="events" id="eventList"></div>
        </section>
      </section>

      <section id="view-settings" class="hide">
        <div class="hero">
          <h1 style="font-size:22px">设置</h1>
          <p>改动即时生效，不需要重启容器。上游地址换完会立刻重建连接。</p>
        </div>
        <div class="group">
          <h3>上游与访问</h3>
          <div class="field">
            <div class="meta"><div class="name">极影视地址</div><div class="hint">例如 http://192.168.2.8:8021，换设备部署时改这里</div></div>
            <input type="url" id="upstream_url" class="wide" placeholder="http://host:port">
            <button class="ghost" id="testBtn">测试连接</button>
            <span class="result" id="testResult"></span>
          </div>
          <div class="field">
            <div class="meta"><div class="name">面板 IP 白名单</div><div class="hint">逗号分隔；留空表示不限制。只影响控制台，不影响播放代理</div></div>
            <input type="text" id="allowed_ips" class="wide" placeholder="192.168.2.0/24 请写成具体 IP">
          </div>
        </div>
        <div class="group">
          <h3>同步行为</h3>
          <div class="field">
            <div class="meta"><div class="name">原生进度写入</div><div class="hint">关闭后只记录到本地库，不再写极影视数据库</div></div>
            <label class="switch"><input type="checkbox" id="native_enabled"><span class="track"></span><span class="knob"></span></label>
          </div>
          <div class="field">
            <div class="meta"><div class="name">已看阈值</div><div class="hint">进度超过这个比例就标记为已看，0.9 表示 90%</div></div>
            <input type="number" id="played_threshold" step="0.01" min="0" max="1">
          </div>
          <div class="field">
            <div class="meta"><div class="name">删除同步宽限期</div><div class="hint">极影视没有记录且本地超过这个秒数，就认为那边删了，本地跟着清</div></div>
            <input type="number" id="sync_grace_seconds" step="1" min="0">
          </div>
        </div>
        <div class="group">
          <h3>写入节奏</h3>
          <div class="field">
            <div class="meta"><div class="name">写库最小间隔</div><div class="hint">秒；播放结束那次上报不受限制</div></div>
            <input type="number" id="native_min_interval" step="1" min="0">
          </div>
          <div class="field">
            <div class="meta"><div class="name">音轨 / 字幕偏好</div><div class="hint">把客户端选的音轨与字幕写回极影视</div></div>
            <label class="switch"><input type="checkbox" id="sync_stream_prefs"><span class="track"></span><span class="knob"></span></label>
          </div>
          <div class="field">
            <div class="meta"><div class="name">日志级别</div><div class="hint">排查问题时用 DEBUG，平时 INFO 就够</div></div>
            <select id="log_level"><option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option></select>
          </div>
        </div>
        <div class="group">
          <h3>安全</h3>
          <div class="field">
            <div class="meta"><div class="name">修改管理密码</div><div class="hint">改完当前会话会续期，其它设备需要重新登录</div></div>
            <input type="password" id="oldPwd" placeholder="原密码">
            <input type="password" id="newPwd" placeholder="新密码（≥6 位）">
            <button class="ghost" id="pwdBtn">修改</button>
            <span class="result" id="pwdResult"></span>
          </div>
          <div class="field">
            <div class="meta"><div class="name">导出配置</div><div class="hint">把当前设置导出成 .env 片段，方便换机器部署</div></div>
            <button class="ghost" id="exportBtn">导出</button>
          </div>
        </div>
      </section>

      <section id="view-tools" class="hide">
        <div class="hero">
          <h1 style="font-size:22px">工具</h1>
          <p>用片名、文件名或 collection_id 查询条目与片头片尾区间。</p>
        </div>
        <section class="block">
          <h2>查询条目 / 片头片尾</h2>
          <div class="tool-row">
            <input type="text" id="query" placeholder="片名、文件名，或 collection_id">
            <button class="ghost" id="searchBtn">查询</button>
          </div>
          <pre class="out" id="searchOut">还没有查询。</pre>
        </section>
        <section class="block">
          <h2>恢复默认</h2>
          <p style="color:var(--dim);font-size:13px;margin:0 0 14px">清除面板里保存的设置，回到环境变量的默认值。日志与本地进度不受影响。</p>
          <button class="danger" id="resetBtn">清除面板设置</button>
        </section>
      </section>
    </div>
  </main>
</div>

<div class="savedbar hide" id="saveBar">
  <div class="inner">
    <span class="txt">设置已修改</span>
    <button class="primary" id="saveBtn">保存更改</button>
    <button class="ghost" id="discardBtn">放弃</button>
  </div>
</div>
<div id="toast" role="status" aria-live="polite"></div>

<script>
const $ = (id) => document.getElementById(id);
let needsSetup = false;
let snapshot = null;
let dirty = false;

async function api(path, options) {
  const opts = Object.assign({credentials:'same-origin'}, options || {});
  if (opts.method && opts.method !== 'GET') {
    opts.headers = Object.assign({'X-Requested-With':'fetch'}, opts.headers || {});
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || ('HTTP ' + res.status));
  return data;
}

function toast(text, isError) {
  const el = $('toast');
  el.textContent = text;
  el.className = 'show' + (isError ? ' err' : '');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.className = isError ? 'err' : ''; }, 2600);
}

function ago(seconds) {
  if (!seconds || seconds <= 0) return '还没有';
  if (seconds < 60) return Math.round(seconds) + ' 秒前';
  if (seconds < 3600) return Math.round(seconds / 60) + ' 分钟前';
  return Math.round(seconds / 3600) + ' 小时前';
}

function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleTimeString('zh-CN', {hour12:false});
}

function labelOf(entry) {
  const title = entry.title || entry.file || (entry.item_id || '').slice(0, 24);
  const sub = entry.title && entry.file ? entry.file : (entry.item_id || '');
  return {title: title, sub: sub};
}

async function boot() {
  const s = await api('/admin/api/session');
  needsSetup = s.needs_setup;
  $('brandVersion').textContent = s.version || '';
  if (s.authenticated) { enterApp(); return; }
  if (s.allowed === false) { $('authHint').textContent = '当前 IP 不在白名单里，请在设置里放行后再访问。'; }
  $('authView').classList.remove('hide');
  $('authTitle').textContent = needsSetup ? '设置管理密码' : '登录';
  $('authHint').textContent = needsSetup
    ? '第一次使用，先给控制台设一个密码（至少 6 位）。'
    : '输入管理密码，进入控制台。';
  $('authBtn').textContent = needsSetup ? '保存并进入' : '进入';
  $('authBtn').onclick = async () => {
    const pwd = $('pwd').value;
    if (pwd.length < 6) { $('authMsg').textContent = '密码至少 6 位'; return; }
    $('authMsg').textContent = '';
    try {
      await api(needsSetup ? '/admin/api/setup' : '/admin/api/login', {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({password: pwd})
      });
      enterApp();
    } catch (e) { $('authMsg').textContent = e.message; }
  };
  $('pwd').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('authBtn').click(); });
}

async function enterApp() {
  $('authView').classList.add('hide');
  $('appView').classList.remove('hide');
  $('logoutBtn').classList.remove('hide');
  $('logoutBtn').onclick = async () => { await api('/admin/api/logout', {method:'POST'}); location.reload(); };
  for (const link of document.querySelectorAll('.side a')) {
    link.onclick = (e) => { e.preventDefault(); switchView(link.dataset.view); };
  }
  if (location.hash) switchView(location.hash.slice(1));
  await loadSettings();
  await refresh();
  setInterval(refresh, 5000);
}

function switchView(name) {
  const views = {overview:'view-overview', settings:'view-settings', tools:'view-tools'};
  if (!views[name]) name = 'overview';
  for (const key of Object.keys(views)) {
    $(views[key]).classList.toggle('hide', key !== name);
    const link = document.querySelector('.side a[data-view="' + key + '"]');
    if (link) link.setAttribute('aria-current', key === name ? 'page' : 'false');
  }
  history.replaceState(null, '', '#' + name);
  $('saveBar').classList.toggle('hide', !(name === 'settings' && dirty));
}

async function refresh() {
  try {
    const s = await api('/admin/api/status');
    const stats = s.stats || {};
    const lastWrite = stats.last_native_at ? (Date.now() / 1000 - stats.last_native_at) : 0;

    const pill = $('pill'), title = $('stateTitle');
    if (!s.native_enabled) {
      pill.className = 'pill warn'; $('pillText').textContent = '写入已暂停';
      title.className = 'warn'; title.innerHTML = '<span class="dot"></span>写入已暂停';
      $('stateSub').textContent = '面板里关掉了原生进度写入，进度只记在本地库。';
    } else if (lastWrite && lastWrite < 90) {
      pill.className = 'pill ok'; $('pillText').textContent = '正在同步';
      title.className = ''; title.innerHTML = '<span class="dot"></span>正在同步';
      $('stateSub').textContent = '最近一次写库 ' + ago(lastWrite) + ' · 上游 ' + s.upstream;
    } else {
      pill.className = 'pill'; $('pillText').textContent = '空闲';
      title.className = ''; title.innerHTML = '<span class="dot"></span>空闲';
      $('stateSub').textContent = (lastWrite ? '最近一次写库 ' + ago(lastWrite) : '还没有写库记录') + ' · 上游 ' + s.upstream;
    }
    $('sideUpstream').textContent = '上游 ' + s.upstream.replace(/^https?:\\/\\//, '');
    $('sideMode').textContent = '模式 ' + s.native_mode + ' · 端口 ' + s.listen_port;

    $('mRecords').textContent = s.progress_records;
    $('mReports').textContent = stats.progress || 0;
    $('mWritten').textContent = stats.native_written || 0;
    const failed = stats.native_failed || 0;
    $('mFailed').textContent = failed;
    $('mFailed').className = 'n' + (failed ? ' err' : '');

    const live = s.sessions || [];
    $('liveBlock').classList.toggle('hide', live.length === 0);
    $('liveList').innerHTML = live.map((entry) => {
      const label = labelOf(entry);
      const pos = ((entry.position_ticks || 0) / 1e7);
      const hh = String(Math.floor(pos / 3600)).padStart(2, '0');
      const mm = String(Math.floor((pos % 3600) / 60)).padStart(2, '0');
      const ss = String(Math.floor(pos % 60)).padStart(2, '0');
      return '<div class="live"><div class="pos">' + hh + ':' + mm + ':' + ss + '</div>' +
             '<div class="meta"><div class="name">' + label.title + '</div><div class="sub">' + label.sub + '</div></div>' +
             '<span class="tag">' + entry.active_for + ' 秒前更新</span></div>';
    }).join('');

    $('recentBody').innerHTML = (s.recent || []).map((e) => {
      const label = labelOf(e);
      const pos = ((e.position_ticks || 0) / 1e7).toFixed(0) + ' 秒';
      const tag = e.played ? '<span class="tag ok">已看</span>' : '<span class="tag">播放中</span>';
      return '<tr><td class="mono">' + fmtTime(e.received_at) + '</td>' +
             '<td><div class="name">' + label.title + '</div><div class="sub">' + label.sub + '</div></td>' +
             '<td class="mono">' + pos + '</td><td>' + tag + '</td></tr>';
    }).join('') || '<tr><td colspan="4" class="empty">还没有同步记录。在 Hills 里播一段就会出现在这里。</td></tr>';

    const events = s.events || [];
    const kindText = {cleared: '极影视记录被清空，本地已同步删除', override: '极影视进度覆盖了本地记录'};
    $('eventList').innerHTML = events.map((ev) => {
      const text = kindText[ev.kind] || ev.detail || ev.kind;
      const when = new Date((ev.ts || 0) * 1000).toLocaleTimeString('zh-CN', {hour12:false});
      return '<div class="event"><span class="when">' + when + '</span><span class="what">' + text +
             (ev.item_id ? '<span class="sub"> · ' + ev.item_id.slice(0, 30) + '</span>' : '') + '</span></div>';
    }).join('') || '<div class="empty">暂无事件。删除极影视记录或进度被覆盖时会记在这里。</div>';
  } catch (e) {
    $('pill').className = 'pill err'; $('pillText').textContent = '连接中断';
    $('stateTitle').className = 'err';
    $('stateTitle').innerHTML = '<span class="dot"></span>连不上控制台';
    $('stateSub').textContent = '会话可能过期，刷新页面重新登录。';
  }
}

async function loadSettings() {
  const cfg = await api('/admin/api/settings');
  snapshot = cfg;
  applySettings(cfg);
  for (const el of document.querySelectorAll('#view-settings input, #view-settings select')) {
    if (['oldPwd','newPwd'].includes(el.id)) continue;
    el.addEventListener('change', markDirty);
    el.addEventListener('input', markDirty);
  }
  $('saveBtn').onclick = saveSettings;
  $('discardBtn').onclick = () => { applySettings(snapshot); dirty = false; syncSaveBar(); toast('已放弃修改'); };

  $('testBtn').onclick = async () => {
    $('testResult').textContent = '测试中';
    $('testResult').className = 'result';
    try {
      const r = await api('/admin/api/upstream/test', {method:'POST'});
      if (r.ok) {
        $('testResult').textContent = (r.server || '极影视') + ' ' + (r.version || '') + ' · ' + r.ms + 'ms';
        $('testResult').className = 'result ok';
      } else {
        $('testResult').textContent = (r.error || ('HTTP ' + r.status)) + ' · ' + r.ms + 'ms';
        $('testResult').className = 'result err';
      }
    } catch (e) { $('testResult').textContent = e.message; $('testResult').className = 'result err'; }
  };

  $('pwdBtn').onclick = async () => {
    try {
      await api('/admin/api/password', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({old: $('oldPwd').value, new: $('newPwd').value})
      });
      $('oldPwd').value = ''; $('newPwd').value = '';
      $('pwdResult').textContent = '已修改'; $('pwdResult').className = 'result ok';
    } catch (e) { $('pwdResult').textContent = e.message; $('pwdResult').className = 'result err'; }
  };

  $('exportBtn').onclick = async () => {
    try {
      const res = await fetch('/admin/api/export', {credentials:'same-origin'});
      const text = await res.text();
      const blob = new Blob([text], {type:'text/plain'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'bridge.env';
      a.click();
      URL.revokeObjectURL(a.href);
      toast('已导出 bridge.env');
    } catch (e) { toast(e.message, true); }
  };

  $('resetBtn').onclick = async () => {
    if (!confirm('清除面板里保存的设置，恢复环境变量默认值？')) return;
    try {
      const r = await api('/admin/api/settings/reset', {method:'POST'});
      snapshot = r.options; applySettings(r.options); dirty = false; syncSaveBar(); toast('已恢复默认');
    } catch (e) { toast(e.message, true); }
  };

  $('searchBtn').onclick = async () => {
    const q = $('query').value.trim();
    if (!q) { $('searchOut').textContent = '先输入片名、文件名或 collection_id。'; return; }
    try {
      const data = await api('/admin/api/skips?q=' + encodeURIComponent(q));
      if (!data.matches.length) { $('searchOut').textContent = '没有找到匹配的条目。'; return; }
      $('searchOut').textContent = data.matches.map((m) => {
        const skips = m.skips && m.skips.length ? JSON.stringify(m.skips) : '（没有片头片尾记录）';
        return (m.title || '(无片名)') + '\\n  collection_id: ' + m.collection_id +
               '\\n  文件: ' + (m.file || '—') + '\\n  片头片尾: ' + skips;
      }).join('\\n\\n');
    } catch (e) { $('searchOut').textContent = e.message; }
  };
}

function applySettings(cfg) {
  $('native_enabled').checked = !!cfg.native_enabled;
  $('sync_stream_prefs').checked = !!cfg.sync_stream_prefs;
  $('played_threshold').value = cfg.played_threshold;
  $('native_min_interval').value = cfg.native_min_interval;
  $('sync_grace_seconds').value = cfg.sync_grace_seconds;
  $('log_level').value = cfg.log_level;
  $('upstream_url').value = cfg.upstream_url || '';
  $('allowed_ips').value = cfg.allowed_ips || '';
}

function markDirty() { dirty = true; syncSaveBar(); }
function syncSaveBar() {
  const visible = dirty && !$('view-settings').classList.contains('hide');
  $('saveBar').classList.toggle('hide', !visible);
}

async function saveSettings() {
  $('saveBtn').disabled = true;
  const payload = {
    native_enabled: $('native_enabled').checked,
    sync_stream_prefs: $('sync_stream_prefs').checked,
    played_threshold: parseFloat($('played_threshold').value),
    native_min_interval: parseFloat($('native_min_interval').value),
    sync_grace_seconds: parseFloat($('sync_grace_seconds').value),
    log_level: $('log_level').value,
    upstream_url: $('upstream_url').value.trim(),
    allowed_ips: $('allowed_ips').value.trim(),
  };
  try {
    const r = await api('/admin/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    snapshot = r.options; dirty = false; syncSaveBar(); toast('设置已保存'); refresh();
  } catch (e) { toast(e.message, true); }
  finally { $('saveBtn').disabled = false; }
}

boot();
</script>
</body>
</html>
"""
