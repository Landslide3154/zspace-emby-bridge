"""面板页面：单文件 HTML（内联 CSS/JS），无构建步骤。"""

ADMIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>极影视进度桥 · 控制台</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--line:#262b36;--fg:#e6e9ef;--dim:#9aa3b2;--accent:#4f8cff;--ok:#3ddc84;--warn:#ffb020;--err:#ff5d5d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px}
h1{font-size:16px;margin:0;font-weight:600}
.badge{font-size:12px;color:var(--dim);border:1px solid var(--line);border-radius:99px;padding:2px 10px}
main{max-width:960px;margin:0 auto;padding:24px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:16px}
.card h2{font-size:14px;margin:0 0 12px;color:var(--dim);font-weight:600;letter-spacing:.04em}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.kv{border:1px solid var(--line);border-radius:10px;padding:12px}
.kv .k{font-size:12px;color:var(--dim)}
.kv .v{font-size:16px;margin-top:4px;word-break:break-all}
label{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px dashed var(--line)}
label:last-child{border-bottom:none}
input[type=number],input[type=password],input[type=text]{background:#0b0d12;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:8px 10px;width:140px}
input[type=checkbox]{width:18px;height:18px;accent-color:var(--accent)}
button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:9px 16px;cursor:pointer;font-weight:600}
button.ghost{background:transparent;border:1px solid var(--line);color:var(--fg)}
button:disabled{opacity:.5;cursor:not-allowed}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--dim);font-weight:500}
.muted{color:var(--dim)}
.err{color:var(--err)}
.ok{color:var(--ok)}
.hide{display:none}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
</style>
</head>
<body>
<header><h1>极影视进度桥</h1><span class="badge" id="ver">…</span><span class="badge" id="who"></span></header>
<main>
  <section id="auth" class="card hide">
    <h2 id="authTitle">登录</h2>
    <p class="muted" id="authHint"></p>
    <div class="row">
      <input type="password" id="pwd" placeholder="密码" autocomplete="current-password">
      <button id="authBtn">继续</button>
      <span id="authMsg" class="err"></span>
    </div>
  </section>

  <section id="dash" class="hide">
    <div class="card">
      <h2>状态</h2>
      <div class="grid" id="stats"></div>
    </div>
    <div class="card">
      <h2>设置（即时生效）</h2>
      <label>原生进度写入<input type="checkbox" id="native_enabled"></label>
      <label>已看阈值（0–1）<input type="number" id="played_threshold" step="0.01" min="0" max="1"></label>
      <label>写库最小间隔（秒）<input type="number" id="native_min_interval" step="1" min="0"></label>
      <label>同步宽限期（秒）<input type="number" id="sync_grace_seconds" step="1" min="0"></label>
      <label>音轨/字幕偏好同步<input type="checkbox" id="sync_stream_prefs"></label>
      <label>日志级别
        <select id="log_level" style="background:#0b0d12;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:8px">
          <option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option>
        </select>
      </label>
      <div class="row" style="margin-top:14px"><button id="saveBtn">保存</button><span id="saveMsg"></span></div>
    </div>
    <div class="card">
      <h2>最近同步</h2>
      <table><thead><tr><th>时间</th><th>条目</th><th>位置</th><th>状态</th></tr></thead><tbody id="recent"></tbody></table>
    </div>
    <div class="card">
      <h2>片头片尾区间（只读）</h2>
      <div class="row"><input type="text" id="skipId" placeholder="collection_id，如 560a79a3e816b6e"><button class="ghost" id="skipBtn">查询</button></div>
      <p id="skipOut" class="muted"></p>
    </div>
    <div class="card row"><button class="ghost" id="logoutBtn">退出登录</button></div>
  </section>
</main>
<script>
const $ = (id) => document.getElementById(id);
let needsSetup = false;

async function api(path, options) {
  const res = await fetch(path, Object.assign({credentials:'same-origin'}, options || {}));
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || ('HTTP ' + res.status));
  return data;
}

async function boot() {
  const session = await api('/admin/api/session');
  needsSetup = session.needs_setup;
  $('ver').textContent = session.version || '';
  if (session.authenticated) { showDash(); }
  else {
    $('auth').classList.remove('hide');
    $('authTitle').textContent = needsSetup ? '首次设置密码' : '登录';
    $('authHint').textContent = needsSetup ? '还没有设置管理密码，先设置一个（至少 6 位）。' : '输入管理密码后进入控制台。';
    $('authBtn').textContent = needsSetup ? '设置并进入' : '登录';
  }
  $('authBtn').onclick = async () => {
    const pwd = $('pwd').value;
    if (pwd.length < 6) { $('authMsg').textContent = '密码至少 6 位'; return; }
    try {
      await api(needsSetup ? '/admin/api/setup' : '/admin/api/login', {
        method:'POST', headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},
        body: JSON.stringify({password: pwd})
      });
      showDash();
    } catch (e) { $('authMsg').textContent = e.message; }
  };
}

async function showDash() {
  $('auth').classList.add('hide');
  $('dash').classList.remove('hide');
  await refresh();
  setInterval(refresh, 5000);
}

function card(k, v, cls) {
  return '<div class="kv"><div class="k">' + k + '</div><div class="v ' + (cls||'') + '">' + v + '</div></div>';
}

async function refresh() {
  try {
    const s = await api('/admin/api/status');
    $('who').textContent = s.native_mode + (s.native_enabled ? '' : ' · 已停写');
    $('stats').innerHTML =
      card('上游', s.upstream) +
      card('本地记录', s.progress_records) +
      card('累计上报', s.stats.progress) +
      card('写库成功', s.stats.native_written, 'ok') +
      card('写库失败', s.stats.native_failed, s.stats.native_failed ? 'err' : '') +
      card('已看回写', s.stats.played);
    const cfg = await api('/admin/api/settings');
    for (const key of ['native_enabled','sync_stream_prefs']) { $(key).checked = !!cfg[key]; }
    for (const key of ['played_threshold','native_min_interval','sync_grace_seconds']) { $(key).value = cfg[key]; }
    $('log_level').value = cfg.log_level;
    $('recent').innerHTML = (s.recent || []).map(e =>
      '<tr><td>' + (e.received_at || '').replace('T',' ').slice(0,19) + '</td><td>' + (e.item_id || '').slice(0,28) +
      '</td><td>' + ((e.position_ticks || 0) / 1e7).toFixed(1) + 's</td><td>' + (e.played ? '已看' : '播放中') + '</td></tr>'
    ).join('') || '<tr><td colspan="4" class="muted">暂无</td></tr>';
  } catch (e) { /* 会话过期时静默 */ }
}

$('saveBtn').onclick = async () => {
  const payload = {
    native_enabled: $('native_enabled').checked,
    played_threshold: parseFloat($('played_threshold').value),
    native_min_interval: parseFloat($('native_min_interval').value),
    sync_grace_seconds: parseFloat($('sync_grace_seconds').value),
    sync_stream_prefs: $('sync_stream_prefs').checked,
    log_level: $('log_level').value,
  };
  try {
    await api('/admin/api/settings', {method:'POST', headers:{'Content-Type':'application/json','X-Requested-With':'fetch'}, body: JSON.stringify(payload)});
    $('saveMsg').textContent = '已保存';
    $('saveMsg').className = 'ok';
  } catch (e) { $('saveMsg').textContent = e.message; $('saveMsg').className = 'err'; }
};

$('skipBtn').onclick = async () => {
  const id = $('skipId').value.trim();
  if (!id) return;
  try {
    const data = await api('/admin/api/skips/' + encodeURIComponent(id));
    $('skipOut').textContent = data.skips.length ? JSON.stringify(data.skips) : '没有记录（Hills 侧也不支持自动跳过，见 README）';
  } catch (e) { $('skipOut').textContent = e.message; }
};

$('logoutBtn').onclick = async () => { await api('/admin/api/logout', {method:'POST', headers:{'X-Requested-With':'fetch'}}); location.reload(); };

boot();
</script>
</body>
</html>
"""
