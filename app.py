import os
import sqlite3

from flask import Flask, g, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(BASE_DIR, "memo.db")
PRODUCTION = os.environ.get("PRODUCTION") == "1"

app = Flask(__name__)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY 환경변수가 없습니다. 배포 환경에서는 반드시 설정해야 합니다.\n"
            '생성 방법: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    SECRET_KEY = "dev-only-insecure-key"

app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=PRODUCTION,
    MAX_CONTENT_LENGTH=64 * 1024,
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        db.commit()


# WSGI 서버(waitress/gunicorn)로 띄우면 __main__ 블록이 실행되지 않으므로 여기서 호출한다.
init_db()


BASE_TEMPLATE = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} · Memo</title>
<style>
  *, *::before, *::after { box-sizing: border-box; }

  :root {
    --bg: #07070f;
    --text: #edecf5;
    --muted: #9c9ab5;
    --faint: #64627d;
    --line: rgba(255,255,255,.09);
    --glass: rgba(255,255,255,.045);
    --violet: #7c5cff;
    --magenta: #b45cff;
    --cyan: #22d3ee;
  }

  html, body { height: 100%; }

  body {
    margin: 0;
    display: flex;
    flex-direction: column;
    overflow-x: hidden;
    background: var(--bg);
    color: var(--text);
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI',
                 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
    -webkit-font-smoothing: antialiased;
  }

  /* ---------- 배경 ---------- */
  .aurora { position: fixed; inset: 0; z-index: -2; overflow: hidden; }

  .blob { position: absolute; border-radius: 50%; filter: blur(100px); }

  .blob-a {
    width: 560px; height: 560px; top: -200px; left: -140px;
    background: rgba(109,74,255,.55);
    animation: drift-a 20s ease-in-out infinite alternate;
  }
  .blob-b {
    width: 480px; height: 480px; top: 8%; right: -160px;
    background: rgba(180,92,255,.40);
    animation: drift-b 24s ease-in-out infinite alternate;
  }
  .blob-c {
    width: 620px; height: 620px; bottom: -280px; left: 28%;
    background: rgba(34,211,238,.22);
    animation: drift-c 28s ease-in-out infinite alternate;
  }

  .grid {
    position: fixed; inset: 0; z-index: -1;
    background-image:
      linear-gradient(rgba(255,255,255,.028) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,.028) 1px, transparent 1px);
    background-size: 58px 58px;
    -webkit-mask-image: radial-gradient(ellipse 90% 60% at 50% 0%, #000 25%, transparent 75%);
    mask-image: radial-gradient(ellipse 90% 60% at 50% 0%, #000 25%, transparent 75%);
  }

  /* ---------- 헤더 ---------- */
  header {
    width: 100%; max-width: 1080px; margin: 0 auto;
    padding: 22px 26px;
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
  }

  .brand {
    display: flex; align-items: center; gap: 11px;
    text-decoration: none; color: var(--text);
    font-size: 16px; font-weight: 750; letter-spacing: -.02em;
  }
  .brand-mark {
    width: 34px; height: 34px; border-radius: 11px;
    display: grid; place-items: center;
    background: linear-gradient(135deg, var(--violet), var(--magenta));
    box-shadow: 0 10px 24px -8px rgba(124,92,255,.85);
  }

  nav { display: flex; align-items: center; gap: 8px; }

  .nav-link {
    padding: 9px 15px; border-radius: 11px;
    font-size: 14px; font-weight: 550; color: var(--muted);
    text-decoration: none;
    transition: color .18s, background .18s;
  }
  .nav-link:hover { color: var(--text); background: rgba(255,255,255,.06); }

  .nav-cta {
    padding: 9px 17px; border-radius: 11px;
    font-size: 14px; font-weight: 650; color: #fff;
    text-decoration: none;
    background: linear-gradient(135deg, var(--violet), var(--magenta));
    box-shadow: 0 10px 24px -10px rgba(124,92,255,.9);
    transition: transform .18s, box-shadow .18s, filter .18s;
  }
  .nav-cta:hover {
    transform: translateY(-1px); filter: brightness(1.08);
    box-shadow: 0 14px 30px -10px rgba(124,92,255,1);
  }

  .chip {
    display: flex; align-items: center; gap: 9px;
    padding: 5px 15px 5px 5px; border-radius: 999px;
    background: var(--glass); border: 1px solid var(--line);
    font-size: 14px; color: var(--muted);
  }
  .chip b { color: var(--text); font-weight: 650; }

  .avatar {
    width: 27px; height: 27px; border-radius: 50%;
    display: grid; place-items: center;
    font-size: 13px; font-weight: 750; color: #fff;
    background: linear-gradient(135deg, var(--violet), var(--cyan));
  }

  /* ---------- 본문 ---------- */
  main {
    flex: 1; width: 100%;
    display: flex; align-items: center; justify-content: center;
    padding: 24px 22px 80px;
  }

  .card {
    width: 100%; max-width: 428px;
    padding: 40px 36px;
    border-radius: 24px;
    border: 1px solid var(--line);
    background: linear-gradient(180deg, rgba(255,255,255,.075), rgba(255,255,255,.025));
    -webkit-backdrop-filter: blur(24px);
    backdrop-filter: blur(24px);
    box-shadow: 0 48px 90px -36px rgba(0,0,0,.9), inset 0 1px 0 rgba(255,255,255,.09);
    animation: rise .6s cubic-bezier(.2,.8,.2,1) both;
  }

  .eyebrow {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 6px 13px; margin-bottom: 18px;
    border-radius: 999px;
    border: 1px solid rgba(124,92,255,.32);
    background: rgba(124,92,255,.12);
    font-size: 11.5px; font-weight: 700; letter-spacing: .09em;
    color: #c9b8ff; text-transform: uppercase;
  }
  .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #22d3ee; box-shadow: 0 0 10px #22d3ee;
    animation: pulse 2s ease-in-out infinite;
  }

  h1 {
    margin: 0 0 9px;
    font-size: 29px; font-weight: 780; letter-spacing: -.035em;
  }
  .sub { margin: 0 0 28px; font-size: 14.5px; line-height: 1.55; color: var(--muted); }

  .field { margin-bottom: 17px; }

  label {
    display: block; margin: 0 0 8px 3px;
    font-size: 12.5px; font-weight: 650; letter-spacing: .01em;
    color: var(--muted);
  }

  input {
    width: 100%; padding: 14px 16px;
    font-family: inherit; font-size: 15px; color: var(--text);
    background: rgba(255,255,255,.04);
    border: 1px solid var(--line); border-radius: 14px;
    outline: none;
    transition: border-color .18s, box-shadow .18s, background .18s;
  }
  input::placeholder { color: var(--faint); }
  input:focus {
    background: rgba(255,255,255,.065);
    border-color: rgba(124,92,255,.8);
    box-shadow: 0 0 0 4px rgba(124,92,255,.15);
  }

  .btn {
    width: 100%; margin-top: 9px; padding: 15px 18px;
    font-family: inherit; font-size: 15px; font-weight: 700; color: #fff;
    background: linear-gradient(135deg, var(--violet), var(--magenta));
    border: 0; border-radius: 14px; cursor: pointer;
    box-shadow: 0 16px 34px -14px rgba(124,92,255,.95);
    transition: transform .18s, box-shadow .18s, filter .18s;
  }
  .btn:hover {
    transform: translateY(-2px); filter: brightness(1.08);
    box-shadow: 0 22px 42px -14px rgba(124,92,255,1);
  }
  .btn:active { transform: translateY(0); }

  .btn-ghost {
    display: block; width: 100%; margin-top: 11px; padding: 14px 18px;
    text-align: center; text-decoration: none;
    font-size: 14.5px; font-weight: 600; color: var(--muted);
    background: rgba(255,255,255,.035);
    border: 1px solid var(--line); border-radius: 14px;
    transition: color .18s, background .18s, border-color .18s;
  }
  .btn-ghost:hover {
    color: var(--text);
    background: rgba(255,255,255,.07);
    border-color: rgba(255,255,255,.16);
  }

  .foot {
    margin: 26px 0 0; padding-top: 22px;
    border-top: 1px solid var(--line);
    text-align: center; font-size: 14px; color: var(--faint);
  }
  .foot a {
    color: #b9a5ff; font-weight: 650; text-decoration: none;
    border-bottom: 1px solid rgba(185,165,255,.32);
    transition: color .18s, border-color .18s;
  }
  .foot a:hover { color: #d6caff; border-color: #d6caff; }

  .alert {
    display: flex; gap: 10px; align-items: flex-start;
    margin-bottom: 22px; padding: 13px 15px;
    border-radius: 14px;
    background: rgba(255,86,110,.10);
    border: 1px solid rgba(255,86,110,.30);
    font-size: 14px; line-height: 1.45; color: #ffadb8;
    animation: shake .42s cubic-bezier(.36,.07,.19,.97) both;
  }
  .alert svg { flex: none; margin-top: 1px; }

  /* ---------- 히어로 ---------- */
  .hero { max-width: 660px; text-align: center; animation: rise .6s cubic-bezier(.2,.8,.2,1) both; }

  .hero h1 {
    margin: 0 0 20px;
    font-size: clamp(36px, 7vw, 60px); line-height: 1.1;
    font-weight: 800; letter-spacing: -.045em;
    background: linear-gradient(135deg, #ffffff 25%, #b9a5ff 62%, #22d3ee 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }
  .hero p {
    margin: 0 auto 36px; max-width: 460px;
    font-size: 16.5px; line-height: 1.65; color: var(--muted);
  }
  .hero-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
  .hero-actions .btn, .hero-actions .btn-ghost { width: auto; margin: 0; padding: 15px 30px; }

  /* ---------- 대시보드 ---------- */
  .welcome { text-align: center; }
  .avatar-lg {
    width: 76px; height: 76px; margin: 0 auto 22px; border-radius: 26px;
    display: grid; place-items: center;
    font-size: 31px; font-weight: 800; color: #fff;
    background: linear-gradient(135deg, var(--violet), var(--cyan));
    box-shadow: 0 22px 48px -18px rgba(124,92,255,.95);
  }
  .status {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 7px 15px; margin-bottom: 26px; border-radius: 999px;
    background: rgba(34,211,238,.1); border: 1px solid rgba(34,211,238,.26);
    font-size: 12.5px; font-weight: 650; color: #7ee7fb;
  }
  .note {
    padding: 17px 19px; margin-bottom: 8px;
    border-radius: 16px; text-align: left;
    background: rgba(255,255,255,.035); border: 1px solid var(--line);
    font-size: 14px; line-height: 1.6; color: var(--muted);
  }
  .note b { display: block; margin-bottom: 4px; color: var(--text); font-weight: 650; }

  /* ---------- 달려오는 무대 ---------- */
  .card-wide { max-width: 560px; }

  .stage {
    position: relative; height: 320px; margin: 4px 0 22px;
    border-radius: 20px; overflow: hidden;
    border: 1px solid var(--line);
    background: linear-gradient(180deg, #0d0a24 0%, #1a1046 46%, #2c1663 100%);
  }
  .stage::after {
    content: ''; position: absolute; left: 0; right: 0; top: 45%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(190,140,255,.95), transparent);
    box-shadow: 0 0 42px 12px rgba(124,92,255,.32);
  }

  .ground {
    position: absolute; left: -60%; right: -60%; bottom: -14%; height: 58%;
    transform: perspective(250px) rotateX(59deg);
    transform-origin: 50% 0%;
    background:
      repeating-linear-gradient(0deg, rgba(255,255,255,.07) 0 7px, transparent 7px 64px),
      linear-gradient(180deg, #2c1663, #09061a);
  }
  .stage.running .ground { animation: road var(--step, .42s) linear infinite; }

  .speedlines {
    position: absolute; inset: -35%; opacity: 0;
    background: repeating-conic-gradient(from 0deg at 50% 50%,
      rgba(255,255,255,.13) 0deg .7deg, transparent .7deg 7deg);
    -webkit-mask-image: radial-gradient(circle at 50% 50%, transparent 16%, #000 62%);
    mask-image: radial-gradient(circle at 50% 50%, transparent 16%, #000 62%);
  }
  .stage.running .speedlines { animation: zoom-lines var(--dur, 1.5s) linear; }

  .runner {
    position: absolute; left: 50%; top: 46%;
    font-size: 92px; line-height: 1;
    transform: translate(-50%, -50%) scale(.5);
    filter: drop-shadow(0 18px 26px rgba(0,0,0,.6));
    transition: transform .4s ease;
    will-change: transform;
  }
  .stage.running .runner {
    animation: approach var(--dur, 1.5s) cubic-bezier(.5, 0, .9, .42) forwards;
  }

  .runner-inner { display: inline-block; animation: idle 2.6s ease-in-out infinite; }
  .stage.running .runner-inner { animation: bob var(--step, .42s) ease-in-out infinite; }

  .bubble {
    position: absolute; left: 50%; bottom: 18px;
    padding: 11px 22px; border-radius: 999px;
    background: rgba(255,255,255,.96); color: #17142b;
    font-size: 15px; font-weight: 750; white-space: nowrap;
    opacity: 0; pointer-events: none;
    transform: translateX(-50%) scale(.75);
    box-shadow: 0 16px 34px -10px rgba(0,0,0,.75);
    transition: opacity .2s, transform .3s cubic-bezier(.2, 1.6, .4, 1);
  }
  .stage.arrived { animation: bump .5s cubic-bezier(.36, .07, .19, .97); }
  .stage.arrived .bubble { opacity: 1; transform: translateX(-50%) scale(1); }

  .hint {
    position: absolute; left: 0; right: 0; bottom: 16px;
    text-align: center; font-size: 13px; color: rgba(255,255,255,.42);
    transition: opacity .2s;
  }
  .stage.running .hint, .stage.arrived .hint { opacity: 0; }

  .picker { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }

  .pick {
    display: flex; flex-direction: column; align-items: center; gap: 7px;
    padding: 15px 8px; cursor: pointer;
    font-family: inherit; font-size: 13px; font-weight: 650; color: var(--muted);
    background: rgba(255,255,255,.035);
    border: 1px solid var(--line); border-radius: 17px;
    transition: color .18s, background .18s, border-color .18s, box-shadow .18s;
  }
  .pick em { font-style: normal; font-size: 29px; line-height: 1; transition: transform .2s; }
  .pick:hover { color: var(--text); background: rgba(255,255,255,.075); }
  .pick:hover em { transform: scale(1.18) rotate(-6deg); }
  .pick.active {
    color: #fff;
    background: rgba(124,92,255,.17);
    border-color: rgba(124,92,255,.72);
    box-shadow: 0 0 0 3px rgba(124,92,255,.13);
  }

  .btn:disabled { opacity: .5; cursor: not-allowed; transform: none; filter: none; }

  .hero-pets { display: flex; gap: 14px; justify-content: center; margin-bottom: 26px; font-size: 40px; }
  .hero-pets span { animation: idle 2.6s ease-in-out infinite; }
  .hero-pets span:nth-child(2) { animation-delay: .35s; }
  .hero-pets span:nth-child(3) { animation-delay: .7s; }

  /* ---------- 애니메이션 ---------- */
  @keyframes rise {
    from { opacity: 0; transform: translateY(18px) scale(.985); }
    to   { opacity: 1; transform: none; }
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; } 50% { opacity: .35; }
  }
  @keyframes shake {
    10%, 90% { transform: translateX(-1px); }
    20%, 80% { transform: translateX(2px); }
    30%, 50%, 70% { transform: translateX(-4px); }
    40%, 60% { transform: translateX(4px); }
  }
  @keyframes drift-a {
    to { transform: translate(120px, 80px) scale(1.15); }
  }
  @keyframes drift-b {
    to { transform: translate(-100px, 140px) scale(.9); }
  }
  @keyframes drift-c {
    to { transform: translate(90px, -110px) scale(1.1); }
  }
  @keyframes road {
    to { background-position: 0 64px, 0 0; }
  }
  @keyframes zoom-lines {
    0%   { opacity: 0; transform: scale(.35); }
    30%  { opacity: .9; }
    100% { opacity: 0; transform: scale(2.8); }
  }
  @keyframes approach {
    0%   { transform: translate(-50%, -50%) scale(.42); }
    100% { transform: translate(-50%, -8%) scale(4.6); }
  }
  @keyframes idle {
    0%, 100% { transform: translateY(0); }
    50%      { transform: translateY(-9%); }
  }
  @keyframes bob {
    0%, 100% { transform: translateY(0) rotate(-6deg); }
    50%      { transform: translateY(-14%) rotate(6deg); }
  }
  @keyframes bump {
    0%, 100% { transform: translate(0, 0); }
    15% { transform: translate(-9px, 5px); }
    30% { transform: translate(8px, -6px); }
    45% { transform: translate(-7px, 4px); }
    60% { transform: translate(5px, -3px); }
    80% { transform: translate(-3px, 1px); }
  }

  /* 장식용 움직임만 끈다. 달려오는 연출은 이 페이지의 본체라 남긴다. */
  @media (prefers-reduced-motion: reduce) {
    .blob, .grid, .dot, .card, .hero,
    .alert, .runner-inner, .hero-pets span,
    .stage.arrived, .stage.running .ground, .stage.running .speedlines {
      animation: none !important;
    }
    .speedlines { display: none; }
  }

  @media (max-width: 520px) {
    header { padding: 18px 18px; }
    .card { padding: 32px 24px; }
  }
</style>
</head>
<body>
  <div class="aurora">
    <span class="blob blob-a"></span>
    <span class="blob blob-b"></span>
    <span class="blob blob-c"></span>
  </div>
  <div class="grid"></div>

  <header>
    <a class="brand" href="{{ url_for('index') }}">
      <span class="brand-mark">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff"
             stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 3h9l5 5v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/>
          <path d="M8 12h8M8 16.5h5"/>
        </svg>
      </span>
      Memo
    </a>

    <nav>
      {% if session.get('username') %}
        <span class="chip">
          <span class="avatar">{{ session['username'][0]|upper }}</span>
          <b>{{ session['username'] }}</b>
        </span>
        <a class="nav-link" href="{{ url_for('logout') }}">로그아웃</a>
      {% else %}
        <a class="nav-link" href="{{ url_for('login') }}">로그인</a>
        <a class="nav-cta" href="{{ url_for('signup') }}">시작하기</a>
      {% endif %}
    </nav>
  </header>

  <main>{{ body|safe }}</main>
</body>
</html>
"""

ALERT = """
{% if error %}
<div class="alert">
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2.2" stroke-linecap="round">
    <circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5h.01"/>
  </svg>
  <span>{{ error }}</span>
</div>
{% endif %}
"""

INDEX_BODY = """
{% if session.get('username') %}
<div class="card card-wide welcome">
  <span class="eyebrow"><span class="dot"></span> Who is coming</span>
  <h1>누가 달려올까?</h1>
  <p class="sub">{{ session['username'] }}님, 친구를 고르고 버튼을 눌러보세요.</p>

  <div class="stage" id="stage">
    <div class="ground"></div>
    <div class="speedlines"></div>
    <div class="runner"><span class="runner-inner" id="face">🐶</span></div>
    <div class="bubble" id="bubble"></div>
    <div class="hint">저 멀리서 달려옵니다</div>
  </div>

  <div class="picker" id="picker">
    <button class="pick active" type="button" data-key="dog"><em>🐶</em>강아지</button>
    <button class="pick" type="button" data-key="cat"><em>🐱</em>고양이</button>
    <button class="pick" type="button" data-key="croc"><em>🐊</em>악어</button>
  </div>

  <button class="btn" type="button" id="go">이리 와! 🏃</button>
  <a class="btn-ghost" href="{{ url_for('logout') }}">로그아웃</a>
</div>

<script>
(function () {
  var CHARS = {
    dog:  { emoji: '🐶', msg: '멍멍! 보고 싶었어!', dur: 1500, step: '.16s' },
    cat:  { emoji: '🐱', msg: '냐옹... 왜 불렀냥?', dur: 2100, step: '.26s' },
    croc: { emoji: '🐊', msg: '쩌억... 배고픈데?', dur: 2900, step: '.36s' }
  };

  var stage  = document.getElementById('stage');
  var face   = document.getElementById('face');
  var bubble = document.getElementById('bubble');
  var go     = document.getElementById('go');
  var picks  = document.getElementById('picker').querySelectorAll('.pick');
  var current = 'dog';
  var busy = false;

  Array.prototype.forEach.call(picks, function (btn) {
    btn.addEventListener('click', function () {
      if (busy) return;
      Array.prototype.forEach.call(picks, function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      current = btn.getAttribute('data-key');
      face.textContent = CHARS[current].emoji;
    });
  });

  go.addEventListener('click', function () {
    if (busy) return;
    busy = true;
    go.disabled = true;

    var c = CHARS[current];
    face.textContent = c.emoji;
    bubble.textContent = c.msg;
    stage.style.setProperty('--dur', c.dur + 'ms');
    stage.style.setProperty('--step', c.step);

    stage.classList.remove('running', 'arrived');
    void stage.offsetWidth;
    stage.classList.add('running');

    window.setTimeout(function () { stage.classList.add('arrived'); }, c.dur);
    window.setTimeout(function () {
      stage.classList.remove('running', 'arrived');
      go.disabled = false;
      busy = false;
    }, c.dur + 1800);
  });
})();
</script>
{% else %}
<div class="hero">
  <span class="eyebrow"><span class="dot"></span> Run to me</span>
  <h1>버튼 한 번에,<br>친구가 달려온다.</h1>
  <div class="hero-pets"><span>🐶</span><span>🐱</span><span>🐊</span></div>
  <p>강아지, 고양이, 악어 중 하나를 고르고 버튼을 누르면
     저 멀리서 당신에게 달려옵니다. 로그인하면 바로 시작해요.</p>
  <div class="hero-actions">
    <a class="btn" href="{{ url_for('signup') }}"
       style="display:inline-block;text-decoration:none;">무료로 시작하기</a>
    <a class="btn-ghost" href="{{ url_for('login') }}">로그인</a>
  </div>
</div>
{% endif %}
"""

SIGNUP_BODY = (
    """
<div class="card">
  <span class="eyebrow"><span class="dot"></span> Create account</span>
  <h1>회원가입</h1>
  <p class="sub">아이디와 비밀번호만 있으면 바로 시작할 수 있어요.</p>
"""
    + ALERT
    + """
  <form method="post">
    <div class="field">
      <label for="username">아이디</label>
      <input id="username" name="username" type="text" placeholder="사용할 아이디"
             autocomplete="username" autofocus>
    </div>
    <div class="field">
      <label for="password">비밀번호</label>
      <input id="password" name="password" type="password" placeholder="비밀번호 입력"
             autocomplete="new-password">
    </div>
    <button class="btn" type="submit">계정 만들기</button>
  </form>
  <p class="foot">이미 계정이 있으신가요?
    <a href="{{ url_for('login') }}">로그인</a>
  </p>
</div>
"""
)

LOGIN_BODY = (
    """
<div class="card">
  <span class="eyebrow"><span class="dot"></span> Welcome back</span>
  <h1>로그인</h1>
  <p class="sub">계정 정보를 입력하고 이어서 기록해보세요.</p>
"""
    + ALERT
    + """
  <form method="post">
    <div class="field">
      <label for="username">아이디</label>
      <input id="username" name="username" type="text" placeholder="아이디"
             autocomplete="username" autofocus>
    </div>
    <div class="field">
      <label for="password">비밀번호</label>
      <input id="password" name="password" type="password" placeholder="비밀번호"
             autocomplete="current-password">
    </div>
    <button class="btn" type="submit">로그인</button>
  </form>
  <p class="foot">아직 계정이 없으신가요?
    <a href="{{ url_for('signup') }}">회원가입</a>
  </p>
</div>
"""
)


def render(body_template, error=None, title="메모"):
    body = render_template_string(body_template, error=error)
    return render_template_string(BASE_TEMPLATE, body=body, title=title)


@app.route("/")
def index():
    return render(INDEX_BODY, title="홈")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render(SIGNUP_BODY, error="아이디와 비밀번호를 모두 입력해주세요.", title="회원가입")

        if len(username) > 20:
            return render(SIGNUP_BODY, error="아이디는 20자 이하로 입력해주세요.", title="회원가입")

        if len(password) < 6:
            return render(SIGNUP_BODY, error="비밀번호는 6자 이상이어야 합니다.", title="회원가입")

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            return render(SIGNUP_BODY, error="이미 존재하는 아이디입니다.", title="회원가입")

        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.commit()
        return redirect(url_for("login"))

    return render(SIGNUP_BODY, title="회원가입")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            return render(LOGIN_BODY, error="아이디 또는 비밀번호가 올바르지 않습니다.", title="로그인")

        session["username"] = user["username"]
        return redirect(url_for("index"))

    return render(LOGIN_BODY, title="로그인")


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0" if PRODUCTION else "127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=not PRODUCTION,
    )
