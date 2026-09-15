import os
import sqlite3

from flask import Flask, g, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(BASE_DIR, "memo.db")
PRODUCTION = os.environ.get("PRODUCTION") == "1"
# 관리자 아이디. 비워두면 아무도 관리자가 아니다(기본값).
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
# 관리자만 볼 수 있는 플래그. 실제 값은 .env(또는 배포 환경변수)에서 주입한다.
FLAG = os.environ.get("FLAG", "FLAG{set_the_FLAG_env_var}")

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


def is_admin():
    return bool(ADMIN_USERNAME) and session.get("username") == ADMIN_USERNAME


@app.context_processor
def inject_admin():
    return {"is_admin": is_admin()}


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
    --green: #03c75a;
    --green-dark: #02b350;
    --green-deep: #0a7c40;
    --green-soft: #eaf8f0;
    --bg: #f5f6f7;
    --panel: #ffffff;
    --text: #222226;
    --muted: #55555f;
    --faint: #8e8e96;
    --line: #e5e5e8;
    --line-strong: #d3d3d8;
  }

  html, body { height: 100%; }

  body {
    margin: 0;
    display: flex;
    flex-direction: column;
    overflow-x: hidden;
    background: var(--bg);
    color: var(--text);
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo',
                 'Malgun Gothic', 'Segoe UI', dotum, sans-serif;
    -webkit-font-smoothing: antialiased;
  }

  /* ---------- 배경 (담백한 회색 배경이라 장식은 감춘다) ---------- */
  .aurora { position: fixed; inset: 0; z-index: -2; background: var(--bg); }
  .blob { display: none; }
  .grid { display: none; }

  /* ---------- 헤더 ---------- */
  header {
    width: 100%; max-width: none; margin: 0;
    height: 58px; flex: none;
    padding: 0 max(20px, calc((100% - 1080px) / 2));
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
    background: var(--panel);
    border-bottom: 1px solid var(--line-strong);
  }

  .brand {
    display: flex; align-items: center; gap: 9px;
    text-decoration: none; color: var(--text);
    font-size: 19px; font-weight: 800; letter-spacing: -.03em;
  }
  .brand-mark {
    width: 30px; height: 30px; border-radius: 7px;
    display: grid; place-items: center;
    background: var(--green);
  }

  nav { display: flex; align-items: center; gap: 6px; }

  .nav-link {
    padding: 8px 12px; border-radius: 6px;
    font-size: 14px; font-weight: 500; color: var(--muted);
    text-decoration: none; white-space: nowrap;
    transition: color .15s, background .15s;
  }
  .nav-link:hover { color: var(--text); background: #f1f2f4; }

  .nav-cta {
    padding: 8px 16px; border-radius: 6px;
    font-size: 14px; font-weight: 700; color: #fff;
    text-decoration: none; white-space: nowrap;
    background: var(--green);
    transition: background .15s;
  }
  .nav-cta:hover { background: var(--green-dark); }

  .chip {
    display: flex; align-items: center; gap: 8px;
    padding: 4px 12px 4px 4px; border-radius: 999px;
    background: #f5f6f7; border: 1px solid var(--line);
    font-size: 13.5px; color: var(--muted); white-space: nowrap;
  }
  .chip b { color: var(--text); font-weight: 700; }

  .avatar {
    width: 26px; height: 26px; border-radius: 50%;
    display: grid; place-items: center;
    font-size: 13px; font-weight: 800; color: #fff;
    background: var(--green);
  }

  /* ---------- 본문 ---------- */
  main {
    flex: 1; width: 100%;
    display: flex; align-items: center; justify-content: center;
    padding: 40px 20px 72px;
  }

  .card {
    width: 100%; max-width: 420px;
    padding: 36px 32px;
    border-radius: 8px;
    border: 1px solid var(--line-strong);
    background: var(--panel);
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
    animation: rise .45s cubic-bezier(.2,.8,.2,1) both;
  }

  .eyebrow {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 11px; margin-bottom: 16px;
    border-radius: 4px;
    border: 1px solid rgba(3,199,90,.3);
    background: var(--green-soft);
    font-size: 11.5px; font-weight: 700; letter-spacing: .06em;
    color: var(--green-deep); text-transform: uppercase;
  }
  .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--green);
    animation: pulse 2s ease-in-out infinite;
  }

  h1 {
    margin: 0 0 8px;
    font-size: 26px; font-weight: 800; letter-spacing: -.03em; color: var(--text);
  }
  .sub { margin: 0 0 26px; font-size: 14px; line-height: 1.6; color: var(--muted); }

  .field { margin-bottom: 14px; }

  label {
    display: block; margin: 0 0 7px 1px;
    font-size: 13px; font-weight: 700; color: var(--muted);
  }

  input {
    width: 100%; padding: 13px 14px;
    font-family: inherit; font-size: 15px; color: var(--text);
    background: #fff;
    border: 1px solid var(--line-strong); border-radius: 4px;
    outline: none;
    transition: border-color .15s, box-shadow .15s;
  }
  input::placeholder { color: #b5b5bc; }
  input:focus {
    border-color: var(--green);
    box-shadow: 0 0 0 2px rgba(3,199,90,.15);
  }

  .btn {
    width: 100%; margin-top: 10px; padding: 15px 18px;
    font-family: inherit; font-size: 15px; font-weight: 700; color: #fff;
    background: var(--green);
    border: 0; border-radius: 6px; cursor: pointer;
    transition: background .15s;
  }
  .btn:hover { background: var(--green-dark); }
  .btn:active { background: #019a45; }

  .btn-ghost {
    display: block; width: 100%; margin-top: 8px; padding: 14px 18px;
    text-align: center; text-decoration: none;
    font-size: 14.5px; font-weight: 600; color: var(--muted);
    background: #fff;
    border: 1px solid var(--line-strong); border-radius: 6px;
    transition: background .15s, border-color .15s, color .15s;
  }
  .btn-ghost:hover { color: var(--text); background: #f7f8f9; border-color: #bcbcc4; }

  .foot {
    margin: 24px 0 0; padding-top: 20px;
    border-top: 1px solid var(--line);
    text-align: center; font-size: 13.5px; color: var(--faint);
  }
  .foot a {
    color: var(--green-deep); font-weight: 700; text-decoration: none;
  }
  .foot a:hover { text-decoration: underline; }

  .alert {
    display: flex; gap: 9px; align-items: flex-start;
    margin-bottom: 20px; padding: 12px 14px;
    border-radius: 4px;
    background: #fff4f4;
    border: 1px solid #f3c9c9;
    font-size: 13.5px; line-height: 1.5; color: #d63b3b;
    animation: shake .42s cubic-bezier(.36,.07,.19,.97) both;
  }
  .alert svg { flex: none; margin-top: 1px; }

  /* ---------- 히어로 ---------- */
  .hero { max-width: 620px; text-align: center; animation: rise .45s cubic-bezier(.2,.8,.2,1) both; }

  .hero h1 {
    margin: 0 0 18px;
    font-size: clamp(32px, 6vw, 52px); line-height: 1.18;
    font-weight: 800; letter-spacing: -.04em;
    color: var(--text);
  }
  .hero p {
    margin: 0 auto 32px; max-width: 440px;
    font-size: 16px; line-height: 1.7; color: var(--muted);
  }
  .hero-actions { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
  .hero-actions .btn, .hero-actions .btn-ghost { width: auto; margin: 0; padding: 15px 30px; }

  /* ---------- 대시보드 ---------- */
  .welcome { text-align: center; }
  .avatar-lg {
    width: 70px; height: 70px; margin: 0 auto 20px; border-radius: 18px;
    display: grid; place-items: center;
    font-size: 29px; font-weight: 800; color: #fff;
    background: var(--green);
  }
  .status {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 13px; margin-bottom: 24px; border-radius: 4px;
    background: var(--green-soft); border: 1px solid rgba(3,199,90,.28);
    font-size: 12.5px; font-weight: 700; color: var(--green-deep);
  }
  .note {
    padding: 15px 17px; margin-bottom: 8px;
    border-radius: 6px; text-align: left;
    background: #f7f8f9; border: 1px solid var(--line);
    font-size: 13.5px; line-height: 1.6; color: var(--muted);
  }
  .note b { display: block; margin-bottom: 4px; color: var(--text); font-weight: 700; }

  /* ---------- 달려오는 무대 ---------- */
  .card-wide { max-width: 560px; }

  .stage {
    position: relative; height: 320px; margin: 4px 0 20px;
    border-radius: 8px; overflow: hidden;
    border: 1px solid var(--line-strong);
    background: linear-gradient(180deg, #f2fbf6 0%, #e3f5ea 46%, #d2eddd 100%);
  }
  .stage::after {
    content: ''; position: absolute; left: 0; right: 0; top: 45%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(3,199,90,.55), transparent);
  }

  .ground {
    position: absolute; left: -60%; right: -60%; bottom: -14%; height: 58%;
    transform: perspective(250px) rotateX(59deg);
    transform-origin: 50% 0%;
    background:
      repeating-linear-gradient(0deg, rgba(255,255,255,.75) 0 7px, transparent 7px 64px),
      linear-gradient(180deg, #cfe9da, #9fd4b8);
  }
  .stage.running .ground { animation: road var(--step, .42s) linear infinite; }

  .speedlines {
    position: absolute; inset: -35%; opacity: 0;
    background: repeating-conic-gradient(from 0deg at 50% 50%,
      rgba(0,0,0,.055) 0deg .7deg, transparent .7deg 7deg);
    -webkit-mask-image: radial-gradient(circle at 50% 50%, transparent 16%, #000 62%);
    mask-image: radial-gradient(circle at 50% 50%, transparent 16%, #000 62%);
  }
  .stage.running .speedlines { animation: zoom-lines var(--dur, 1.5s) linear; }

  .runner {
    position: absolute; left: 50%; top: 46%;
    font-size: 92px; line-height: 1;
    transform: translate(-50%, -50%) scale(.5);
    filter: drop-shadow(0 14px 18px rgba(0,0,0,.22));
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
    padding: 10px 20px; border-radius: 999px;
    background: #fff; color: var(--text);
    border: 1px solid var(--line-strong);
    font-size: 15px; font-weight: 700; white-space: nowrap;
    opacity: 0; pointer-events: none;
    transform: translateX(-50%) scale(.75);
    box-shadow: 0 6px 16px -6px rgba(0,0,0,.28);
    transition: opacity .2s, transform .3s cubic-bezier(.2, 1.6, .4, 1);
  }
  .stage.arrived { animation: bump .5s cubic-bezier(.36, .07, .19, .97); }
  .stage.arrived .bubble { opacity: 1; transform: translateX(-50%) scale(1); }

  .hint {
    position: absolute; left: 0; right: 0; bottom: 16px;
    text-align: center; font-size: 13px; color: #7d9a8b;
    transition: opacity .2s;
  }
  .stage.running .hint, .stage.arrived .hint { opacity: 0; }

  .picker { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px; }

  .pick {
    display: flex; flex-direction: column; align-items: center; gap: 6px;
    padding: 14px 8px; cursor: pointer;
    font-family: inherit; font-size: 13px; font-weight: 700; color: var(--muted);
    background: #fff;
    border: 1px solid var(--line-strong); border-radius: 6px;
    transition: color .15s, background .15s, border-color .15s;
  }
  .pick em { font-style: normal; font-size: 28px; line-height: 1; transition: transform .2s; }
  .pick:hover { background: #f7f8f9; border-color: #bcbcc4; }
  .pick:hover em { transform: scale(1.15) rotate(-6deg); }
  .pick.active {
    color: var(--green-deep);
    background: var(--green-soft);
    border-color: var(--green);
  }

  .btn:disabled { background: #c9cbd0; cursor: not-allowed; }

  /* ---------- 관리자 ---------- */
  .card-admin { max-width: 640px; }

  .flag-box {
    margin: 4px 0 24px; padding: 17px 19px; border-radius: 6px;
    background: var(--green-soft);
    border: 1px solid rgba(3,199,90,.45);
  }
  .flag-box b {
    display: block; margin-bottom: 8px;
    font-size: 11.5px; font-weight: 700; letter-spacing: .06em;
    text-transform: uppercase; color: var(--green-deep);
  }
  .flag-box code {
    display: block; font-size: 16px; font-weight: 700;
    letter-spacing: .01em; color: var(--green-deep);
  }
  .flag-box .desc { display: block; margin-top: 9px; font-size: 12.5px; color: var(--muted); }

  .table-wrap { overflow-x: auto; margin-bottom: 8px; }

  .flags {
    width: 100%; table-layout: fixed;
    border-collapse: collapse; text-align: left; font-size: 13.5px;
  }
  .flags th {
    padding: 0 12px 9px; font-size: 11.5px; font-weight: 700;
    letter-spacing: .06em; text-transform: uppercase; color: var(--faint);
  }
  .flags th:first-child, .flags td:first-child { width: 40%; }
  .flags td { padding: 12px; border-top: 1px solid var(--line); vertical-align: top; }
  .flags .desc { display: block; margin-top: 5px; font-size: 12.5px; color: var(--faint); }

  code {
    font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
    font-size: 12.5px; color: var(--green-deep); word-break: break-all;
  }

  .tag {
    display: inline-block; margin-left: 6px; padding: 2px 9px; border-radius: 3px;
    font-size: 11px; font-weight: 700; white-space: nowrap; vertical-align: 1px;
  }
  .tag-ok   { background: var(--green-soft); border: 1px solid rgba(3,199,90,.35); color: var(--green-deep); }
  .tag-warn { background: #fff6e8; border: 1px solid #f0cf9a; color: #b8730d; }

  .hero-pets { display: flex; gap: 14px; justify-content: center; margin-bottom: 24px; font-size: 40px; }
  .hero-pets span { animation: idle 2.6s ease-in-out infinite; }
  .hero-pets span:nth-child(2) { animation-delay: .35s; }
  .hero-pets span:nth-child(3) { animation-delay: .7s; }

  /* ---------- 애니메이션 ---------- */
  @keyframes rise {
    from { opacity: 0; transform: translateY(14px); }
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
    .dot, .card, .hero,
    .alert, .runner-inner, .hero-pets span,
    .stage.arrived, .stage.running .ground, .stage.running .speedlines {
      animation: none !important;
    }
    .speedlines { display: none; }
  }

  @media (max-width: 520px) {
    header { padding: 0 14px; gap: 6px; }
    nav { gap: 2px; }
    .brand { font-size: 17px; gap: 7px; }
    .nav-link { padding: 8px 8px; }
    .nav-cta { padding: 8px 12px; }
    .chip { padding: 3px 9px 3px 3px; font-size: 13px; }
    main { padding: 24px 16px 56px; }
    .card { padding: 28px 22px; }
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
        {% if is_admin %}
          <a class="nav-link" href="{{ url_for('admin') }}">관리자</a>
        {% endif %}
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


ADMIN_BODY = """
<div class="card card-admin">
  <span class="eyebrow"><span class="dot"></span> Admin only</span>
  <h1>관리자 전용</h1>
  <p class="sub">이 페이지는 관리자 계정으로 로그인해야만 열립니다.</p>

  <div class="flag-box">
    <b>Flag</b>
    <code>{{ flag }}</code>
    <span class="desc">관리자가 아닌 사용자는 이 값을 볼 수 없습니다.</span>
  </div>

  <h2 class="sub" style="margin-bottom:14px">서버 보안 설정</h2>

  <div class="table-wrap">
    <table class="flags">
      <thead>
        <tr><th>항목</th><th>현재 값</th></tr>
      </thead>
      <tbody>
        {% for f in flags %}
        <tr>
          <td><code>{{ f.name }}</code></td>
          <td>
            <code>{{ f.value }}</code>
            <span class="tag {{ 'tag-ok' if f.ok else 'tag-warn' }}">{{ '정상' if f.ok else '확인 필요' }}</span>
            <span class="desc">{{ f.desc }}</span>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="note">
    <b>브라우저가 실제로 받는 헤더</b>
    <code>Set-Cookie: session=...; {{ cookie_header }}</code>
  </div>

  <a class="btn-ghost" href="{{ url_for('index') }}">홈으로</a>
</div>
"""

FORBIDDEN_BODY = """
<div class="card welcome">
  <div class="avatar-lg">🔒</div>
  <h1>접근 권한이 없습니다</h1>
  <p class="sub">이 페이지는 관리자만 볼 수 있습니다.</p>
  <a class="btn-ghost" href="{{ url_for('index') }}">홈으로</a>
</div>
"""


def render(body_template, error=None, title="메모", **ctx):
    body = render_template_string(body_template, error=error, **ctx)
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


@app.route("/admin")
def admin():
    if not session.get("username"):
        return redirect(url_for("login"))

    if not is_admin():
        return render(FORBIDDEN_BODY, title="접근 불가"), 403

    secure = app.config["SESSION_COOKIE_SECURE"]
    samesite = app.config["SESSION_COOKIE_SAMESITE"]
    httponly = app.config["SESSION_COOKIE_HTTPONLY"]
    from_env = bool(os.environ.get("SECRET_KEY"))

    flags = [
        {
            "name": "PRODUCTION",
            "value": "1 (배포)" if PRODUCTION else "미설정 (개발)",
            "desc": "나머지 보안 설정의 기준이 되는 값",
            "ok": True,
        },
        {
            "name": "SESSION_COOKIE_SECURE",
            "value": str(secure),
            "desc": "켜지면 HTTPS 연결에서만 세션 쿠키를 보냅니다.",
            "ok": secure == PRODUCTION,
        },
        {
            "name": "SESSION_COOKIE_HTTPONLY",
            "value": str(httponly),
            "desc": "자바스크립트가 쿠키를 읽지 못하게 막습니다 (XSS 방어).",
            "ok": httponly,
        },
        {
            "name": "SESSION_COOKIE_SAMESITE",
            "value": str(samesite),
            "desc": "다른 사이트에서 넘어온 요청에는 쿠키를 싣지 않습니다 (CSRF 방어).",
            "ok": samesite in ("Lax", "Strict"),
        },
        {
            "name": "DEBUG",
            "value": str(app.debug),
            "desc": "배포 환경에서 켜져 있으면 원격 코드 실행이 가능해집니다.",
            "ok": not (PRODUCTION and app.debug),
        },
        {
            "name": "SECRET_KEY",
            "value": "환경변수에서 로드됨" if from_env else "개발용 기본값",
            "desc": "세션 서명에 쓰는 키입니다. 값 자체는 표시하지 않습니다.",
            "ok": from_env,
        },
        {
            "name": "MAX_CONTENT_LENGTH",
            "value": f"{app.config['MAX_CONTENT_LENGTH'] // 1024} KB",
            "desc": "이보다 큰 요청 본문은 거부합니다.",
            "ok": True,
        },
        {
            "name": "DATABASE_PATH",
            "value": DB_PATH,
            "desc": "회원 정보가 저장되는 SQLite 파일 위치",
            "ok": True,
        },
        {
            "name": "request.scheme",
            "value": request.scheme,
            "desc": "지금 이 페이지를 연 실제 프로토콜",
            "ok": request.scheme == "https" or not PRODUCTION,
        },
    ]

    parts = []
    if secure:
        parts.append("Secure")
    if httponly:
        parts.append("HttpOnly")
    parts.append("Path=/")
    if samesite:
        parts.append(f"SameSite={samesite}")

    return render(
        ADMIN_BODY,
        title="관리자",
        flag=FLAG,
        flags=flags,
        cookie_header="; ".join(parts),
    )


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
