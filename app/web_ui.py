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
  --radius:14px; --radius-sm:9px;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{
  background:var(--ink); color:var(--fg);
  font:14px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;
}
a{color:var(--accent);text-decoration:none}
button{font:inherit;color:inherit;cursor:pointer}
input,select{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}
.hide{display:none !important}

/* ---------- 顶栏 ---------- */
.topbar{display:flex;align-items:center;gap:12px;padding:14px 26px;border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(11,14,20,.92);backdrop-filter:blur(10px);z-index:20}
.brand{display:flex;align-items:center;gap:10px;min-width:0}
.brand img{width:30px;height:30px;border-radius:8px;display:block}
.brand b{font-weight:650;letter-spacing:.01em}
.brand span{color:var(--faint);font-size:12px}
.spacer{flex:1}
.pill{display:inline-flex;align-items:center;gap:7px;padding:5px 11px;border:1px solid var(--line);border-radius:999px;font-size:12.5px;color:var(--dim)}
.pill .dot{width:7px;height:7px;border-radius:50%;background:var(--faint)}
.pill.ok .dot{background:var(--ok);box-shadow:0 0 0 4px rgba(62,213,152,.12)}
.pill.warn .dot{background:var(--warn);box-shadow:0 0 0 4px rgba(242,179,65,.12)}
.pill.err .dot{background:var(--err);box-shadow:0 0 0 4px rgba(240,97,109,.12)}
.ghost{background:transparent;border:1px solid var(--line);border-radius:9px;padding:7px 13px;color:var(--dim)}
.ghost:hover{color:var(--fg);border-color:#2C3648}

/* ---------- 布局 ---------- */
.shell{display:flex;min-height:calc(100% - 59px)}
.side{width:212px;flex:0 0 212px;border-right:1px solid var(--line);padding:22px 14px;display:flex;flex-direction:column;gap:4px}
.side a{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:9px;color:var(--dim);position:relative;font-size:13.5px}
.side a:hover{background:var(--surface);color:var(--fg)}
.side a[aria-current="page"]{background:var(--accent-soft);color:#CFD8FF}
.side a[aria-current="page"]::before{content:"";position:absolute;left:0;top:9px;bottom:9px;width:2px;border-radius:2px;background:var(--accent)}
.side .svg{width:17px;height:17px;flex:0 0 17px;opacity:.9}
.side .foot{margin-top:auto;padding:12px;color:var(--faint);font-size:12px;line-height:1.5}
main{flex:1;min-width:0;padding:30px 32px 120px}
.wrap{max-width:880px;margin:0 auto}

/* ---------- 概览 ---------- */
.hero{padding-bottom:22px;border-bottom:1px solid var(--line)}
.hero h1{margin:0;font-size:27px;line-height:1.28;font-weight:650;letter-spacing:-.01em;display:flex;align-items:center;gap:12px}
.hero h1 .dot{width:10px;height:10px;border-radius:50%;background:var(--ok);flex:0 0 10px;animation:pulse 2.4s ease-in-out infinite}
.hero h1.warn .dot{background:var(--warn)}
.hero h1.err .dot{background:var(--err)}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(62,213,152,.28)}50%{box-shadow:0 0 0 7px rgba(62,213,152,0)}}
.hero p{margin:9px 0 0;color:var(--dim);font-size:13.5px}
.hero code{font-family:ui-monospace,SFMono-Regular,"SF Mono",Consolas,monospace;font-size:12.5px;color:#B9C3D6;background:var(--surface);padding:2px 7px;border-radius:6px}

.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:0;padding:22px 0 6px}
.metric{padding:2px 20px;border-left:1px solid var(--line)}
.metric:first-child{padding-left:0;border-left:0}
.metric .n{font-family:ui-monospace,SFMono-Regular,"SF Mono",Consolas,monospace;font-size:24px;line-height:1.2;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.metric .l{color:var(--faint);font-size:12.5px;margin-top:3px}
.metric .n.ok{color:var(--ok)} .metric .n.err{color:var(--err)}

section.block{margin-top:34px}
section.block > h2{font-size:13px;font-weight:600;color:var(--dim);margin:0 0 12px;display:flex;align-items:center;gap:10px}
section.block > h2::after{content:"";flex:1;height:1px;background:var(--line-soft)}

/* ---------- 表格 ---------- */
.table-wrap{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:13px}
thead th{text-align:left;font-weight:500;color:var(--faint);padding:10px 14px;background:var(--surface);border-bottom:1px solid var(--line);white-space:nowrap}
tbody td{padding:11px 14px;border-bottom:1px solid var(--line-soft);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:rgba(255,255,255,.015)}
.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Consolas,monospace;font-variant-numeric:tabular-nums;font-size:12.5px;color:#C5CEDF}
.item{max-width:340px;overflow:hidden;text-overflow:ellipsis;color:#D8DFEC}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11.5px;border:1px solid var(--line);color:var(--dim)}
.tag.ok{color:var(--ok);border-color:rgba(62,213,152,.3);background:rgba(62,213,152,.07)}
.empty{padding:26px 14px;text-align:center;color:var(--faint);font-size:13px}

/* ---------- 设置 ---------- */
.group{border-top:1px solid var(--line-soft);padding:4px 0 8px}
.group:first-of-type{border-top:0}
.group h3{font-size:12.5px;color:var(--faint);font-weight:500;margin:18px 0 6px}
.field{display:flex;align-items:center;gap:18px;padding:13px 0;border-bottom:1px solid var(--line-soft)}
.field:last-child{border-bottom:0}
.field .meta{flex:1;min-width:0}
.field .name{font-size:13.5px}
.field .hint{color:var(--faint);font-size:12.5px;margin-top:2px}
.field input[type=number],.field input[type=text],.field select{
  width:150px;background:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px 10px;text-align:right}
.field input:focus,.field select:focus{border-color:var(--accent)}
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
@media (prefers-reduced-motion:reduce){*{animation:none !important;transition:none !important}}

/* ---------- 工具 ---------- */
.tool-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.tool-row input{flex:1;min-width:220px;background:var(--ink);border:1px solid var(--line);border-radius:9px;padding:9px 12px}
pre.out{margin:14px 0 0;padding:14px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:#C5CEDF;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12.5px;white-space:pre-wrap}

/* ---------- 登录/设置密码 ---------- */
.auth{max-width:380px;margin:64px auto;padding:0 24px}
.auth .card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:26px}
.auth img{width:44px;height:44px;border-radius:11px;display:block;margin-bottom:16px}
.auth h1{font-size:19px;margin:0 0 6px;font-weight:650}
.auth p{color:var(--dim);font-size:13px;margin:0 0 20px}
.auth input{width:100%;background:var(--ink);border:1px solid var(--line);border-radius:9px;padding:11px 12px;margin-bottom:12px}
.auth button{width:100%}
.msg{color:var(--err);font-size:12.5px;min-height:18px;margin:8px 0 0}

/* ---------- toast ---------- */
#toast{position:fixed;left:50%;bottom:26px;transform:translate(-50%,14px);opacity:0;pointer-events:none;
  background:#1B2230;border:1px solid var(--line);border-radius:10px;padding:10px 16px;font-size:13px;
  transition:opacity .2s,transform .2s;z-index:40;box-shadow:0 12px 30px rgba(0,0,0,.4)}
#toast.show{opacity:1;transform:translate(-50%,0)}
#toast.err{border-color:rgba(240,97,109,.4);color:#FFD5D8}

/* ---------- 响应式 ---------- */
@media (max-width:860px){
  .shell{display:block}
  .side{width:auto;flex:none;border-right:0;border-bottom:1px solid var(--line);padding:8px 14px;flex-direction:row;overflow-x:auto;gap:2px}
  .side a{padding:8px 12px;white-space:nowrap}
  .side a[aria-current="page"]::before{display:none}
  .side .foot{display:none}
  main{padding:22px 18px 130px}
  .hero h1{font-size:22px}
  .metrics{grid-template-columns:repeat(2,1fr);row-gap:18px}
  .metric{padding:0 14px}
  .metric:nth-child(odd){border-left:0;padding-left:0}
  .item{max-width:180px}
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

<!-- 登录 / 首次设置 -->
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

<!-- 控制台 -->
<div class="shell hide" id="appView">
  <nav class="side">
    <a href="#overview" data-view="overview" aria-current="page">
      <svg class="svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 13h5l2 4 3-9 2 5h4"/></svg>概览</a>
    <a href="#settings" data-view="settings">
      <svg class="svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3.2"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/></svg>设置</a>
    <a href="#tools" data-view="tools">
      <svg class="svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14.5 4.5a4 4 0 0 0 5 5L11 18H6v-5z"/></svg>工具</a>
    <div class="foot"><div id="sideUpstream"></div><div id="sideMode"></div></div>
  </nav>

  <main>
    <div class="wrap">
      <!-- 概览 -->
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
        <section class="block">
          <h2>最近同步</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>时间</th><th>条目</th><th>位置</th><th>状态</th></tr></thead>
              <tbody id="recentBody"></tbody>
            </table>
          </div>
        </section>
      </section>

      <!-- 设置 -->
      <section id="view-settings" class="hide">
        <div class="hero">
          <h1 style="font-size:22px">设置</h1>
          <p>改动即时生效，不需要重启容器。留空项回落到环境变量。</p>
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
      </section>

      <!-- 工具 -->
      <section id="view-tools" class="hide">
        <div class="hero">
          <h1 style="font-size:22px">工具</h1>
          <p>片头片尾区间只有极影视记录了，Emby 没有标准接口，Hills 也不会主动请求，所以这里只读展示。</p>
        </div>
        <section class="block">
          <h2>查询片头片尾</h2>
          <div class="tool-row">
            <input type="text" id="skipId" placeholder="填写 collection_id，例如 560a79a3e816b6e">
            <button class="ghost" id="skipBtn">查询</button>
          </div>
          <pre class="out" id="skipOut">还没有查询。</pre>
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
  if (isNaN(d)) return iso;
  return d.toLocaleTimeString('zh-CN', {hour12:false});
}

async function boot() {
  const s = await api('/admin/api/session');
  needsSetup = s.needs_setup;
  $('brandVersion').textContent = s.version || '';
  if (s.authenticated) { enterApp(); return; }
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
  $('logoutBtn').onclick = async () => {
    await api('/admin/api/logout', {method:'POST'});
    location.reload();
  };
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
    const polled = s.uptime_seconds || 0;
    const lastWrite = stats.last_native_at ? (Date.now() / 1000 - stats.last_native_at) : 0;
    const lastReport = stats.last_progress_at ? (Date.now() / 1000 - stats.last_progress_at) : 0;

    const pill = $('pill');
    const title = $('stateTitle');
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
      $('stateSub').textContent = lastWrite
        ? '最近一次写库 ' + ago(lastWrite) + ' · 上游 ' + s.upstream
        : '还没有写库记录 · 上游 ' + s.upstream;
    }
    $('sideUpstream').textContent = '上游 ' + s.upstream.replace('http://', '');
    $('sideMode').textContent = '模式 ' + s.native_mode + (s.native_enabled ? '' : ' · 暂停');

    $('mRecords').textContent = s.progress_records;
    $('mReports').textContent = stats.progress || 0;
    $('mWritten').textContent = stats.native_written || 0;
    const failed = stats.native_failed || 0;
    $('mFailed').textContent = failed;
    $('mFailed').className = 'n' + (failed ? ' err' : '');

    const rows = (s.recent || []).map((e) => {
      const pos = ((e.position_ticks || 0) / 1e7).toFixed(0) + ' 秒';
      const item = (e.item_id || '').replace(/^collection_/, '').slice(0, 34);
      const tag = e.played ? '<span class="tag ok">已看</span>' : '<span class="tag">播放中</span>';
      return '<tr><td class="mono">' + fmtTime(e.received_at) + '</td><td class="item">' + item +
             '</td><td class="mono">' + pos + '</td><td>' + tag + '</td></tr>';
    }).join('');
    $('recentBody').innerHTML = rows || '<tr><td colspan="4" class="empty">还没有同步记录。在 Hills 里播一段就会出现在这里。</td></tr>';
  } catch (e) {
    const pill = $('pill');
    pill.className = 'pill err'; $('pillText').textContent = '连接中断';
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
    el.addEventListener('change', markDirty);
    el.addEventListener('input', markDirty);
  }
  $('saveBtn').onclick = saveSettings;
  $('discardBtn').onclick = () => { applySettings(snapshot); dirty = false; syncSaveBar(); toast('已放弃修改'); };
  $('resetBtn').onclick = async () => {
    if (!confirm('清除面板里保存的设置，恢复环境变量默认值？')) return;
    try { const r = await api('/admin/api/settings/reset', {method:'POST'}); snapshot = r.options; applySettings(r.options); dirty = false; syncSaveBar(); toast('已恢复默认'); }
    catch (e) { toast(e.message, true); }
  };
  $('skipBtn').onclick = async () => {
    const id = $('skipId').value.trim();
    if (!id) { $('skipOut').textContent = '先填一个 collection_id。'; return; }
    try {
      const data = await api('/admin/api/skips/' + encodeURIComponent(id));
      $('skipOut').textContent = data.skips.length
        ? JSON.stringify(data.skips, null, 2)
        : '库里没有这条的片头片尾记录。';
    } catch (e) { $('skipOut').textContent = e.message; }
  };
}

function applySettings(cfg) {
  $('native_enabled').checked = !!cfg.native_enabled;
  $('sync_stream_prefs').checked = !!cfg.sync_stream_prefs;
  $('played_threshold').value = cfg.played_threshold;
  $('native_min_interval').value = cfg.native_min_interval;
  $('sync_grace_seconds').value = cfg.sync_grace_seconds;
  $('log_level').value = cfg.log_level;
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
