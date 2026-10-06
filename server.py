# -*- coding: utf-8 -*-
"""
个人学习生活平台 - 本地服务器
使用 Python 标准库，无需安装任何第三方包。

功能：
  - 读取 data/plans 下每日计划并渲染网页
  - 今日 / 日历 / 饮食 / 学习 / 健身 / 复盘 页面
  - 简单的完成打卡（保存到 data/logs）
  - 一键生成今天计划

启动：python agent/server.py
访问：http://localhost:8000
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
PLANS_DIR = os.path.join(BASE_DIR, "data", "plans")
LOGS_DIR = os.path.join(BASE_DIR, "data", "logs")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "profile.json")
GENERATE_SCRIPT = os.path.join(BASE_DIR, "agent", "generate_daily.py")

WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

HOST = "127.0.0.1"
PORT = 8000


# ---------------- 数据层 ----------------

def ensure_dirs():
    os.makedirs(PLANS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


def load_plan(date_str):
    path = os.path.join(PLANS_DIR, date_str + ".json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_plan_dates():
    if not os.path.isdir(PLANS_DIR):
        return []
    files = [f for f in os.listdir(PLANS_DIR) if f.endswith(".json")]
    return sorted(files, reverse=True)


def load_log(date_str):
    path = os.path.join(LOGS_DIR, date_str + ".json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"diet": {}, "study": {}, "fitness": {}, "notes": "", "weight": "", "rating": ""}


def save_log(date_str, log):
    path = os.path.join(LOGS_DIR, date_str + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def load_profile():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def run_generate(date_str=None):
    """调用生成脚本，返回 (成功, 输出文本)。"""
    cmd = [sys.executable, GENERATE_SCRIPT]
    if date_str:
        # 通过环境变量传递日期，供生成脚本读取（标准脚本按当前日期，这里提供接口）
        pass
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR, timeout=30)
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return False, str(e)


# ---------------- 模板渲染 ----------------

def render_template(name, context):
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    # 简单占位替换 {{ key }}
    for k, v in context.items():
        html = html.replace("{{ " + k + " }}", str(v) if v is not None else "")
    # 条件块 {{#if key}}...{{/if}}
    html = render_blocks(html, context)
    return html


def render_blocks(html, ctx):
    # 支持 {{#if key}}...{{/if}} 与 {{#each arr}}...{{/each}}
    def if_repl(m):
        key = m.group(1).strip()
        body = m.group(2)
        val = ctx.get(key)
        if val and (not isinstance(val, (list, dict)) or val):
            return render_simple(body, ctx)
        return ""
    html = re.sub(r"\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}", if_repl, html, flags=re.S)

    def each_repl(m):
        key = m.group(1).strip()
        body = m.group(2)
        arr = ctx.get(key)
        if not isinstance(arr, list):
            return ""
        out = []
        for item in arr:
            if isinstance(item, dict):
                merged = dict(ctx)
                merged.update({kk: vv for kk, vv in item.items()})
                out.append(render_simple(body, merged))
            else:
                out.append(render_simple(body, ctx))
        return "".join(out)
    html = re.sub(r"\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}", each_repl, html, flags=re.S)
    return html


def render_simple(html, ctx):
    for k, v in ctx.items():
        if isinstance(v, (str, int, float)):
            html = html.replace("{{ " + k + " }}", str(v))
    return html


# ---------------- 页面构建 ----------------

def today_date():
    return datetime.now().strftime("%Y-%m-%d")


def common_context(active="today"):
    return {
        "active_today": "active" if active == "today" else "",
        "active_calendar": "active" if active == "calendar" else "",
        "active_diet": "active" if active == "diet" else "",
        "active_study": "active" if active == "study" else "",
        "active_fitness": "active" if active == "fitness" else "",
        "active_review": "active" if active == "review" else "",
        "today_date": today_date(),
        "name": load_profile().get("name", "我"),
    }


def page_head(title, active):
    ctx = common_context(active)
    ctx["title"] = title
    with open(os.path.join(TEMPLATES_DIR, "head.html"), "r", encoding="utf-8") as f:
        head = f.read()
    with open(os.path.join(TEMPLATES_DIR, "nav.html"), "r", encoding="utf-8") as f:
        nav = f.read()
    return render_simple(head, ctx) + render_simple(nav, ctx)


def page_foot():
    with open(os.path.join(TEMPLATES_DIR, "foot.html"), "r", encoding="utf-8") as f:
        return f.read()


def render_today(date_str=None):
    if not date_str:
        date_str = today_date()
    plan = load_plan(date_str)
    log = load_log(date_str)
    if not plan:
        # 当天没有计划，提示生成
        ctx = common_context("today")
        html = page_head("今日计划", "today")
        html += f"""
        <main class="container"><div class="card warn">
          <h2>今天（{date_str}）还没有计划</h2>
          <p>点击下方按钮生成今天的饮食、学习、健身计划。</p>
          <button onclick="location.href='/generate?date={date_str}'">生成今天计划</button>
        </div></main>"""
        html += page_foot()
        return html

    ctx = common_context("today")
    ctx.update({
        "date": plan["date"],
        "weekday": plan["weekday"],
        "diet_goal": plan["diet"]["goal"],
        "diet_target_cals": plan["diet"]["target"]["calories"],
        "diet_target_pro": plan["diet"]["target"]["protein_g"],
        "diet_est_cals": plan["diet"]["summary"]["estimated_calories"],
        "diet_est_pro": plan["diet"]["summary"]["estimated_protein_g"],
        "study_theme": plan["study"]["theme"],
        "study_goal": plan["study"]["goal"],
        "fitness_session": plan["fitness"]["session"],
        "fitness_type": plan["fitness"]["type"],
        "fitness_duration": plan["fitness"]["duration_minutes"],
        "water": plan["review"]["water_target_liters"],
        "sleep": plan["review"]["sleep_target"],
        "wake": plan["review"]["wake_target"],
    })
    # 三餐
    meals_html = ""
    for m in plan["diet"]["meals"]:
        checked = "checked" if log["diet"].get(m["meal"]) else ""
        meals_html += f"""
        <div class="meal">
          <label><input type="checkbox" data-cat="diet" data-key="{m['meal']}" {checked}>
            <strong>{m['meal']}</strong> · {m['dish']}</label>
          <span class="meta">约 {m['calories']} kcal / {m['protein_g']}g 蛋白</span>
        </div>"""
    ctx["meals_html"] = meals_html

    tasks_html = ""
    for i, t in enumerate(plan["study"]["tasks"]):
        key = f"task{i}"
        checked = "checked" if log["study"].get(key) else ""
        tasks_html += f"""
        <div class="task">
          <label><input type="checkbox" data-cat="study" data-key="{key}" {checked}>
            <strong>{t['task']}</strong> · {t['target']}</label>
          <p class="tip">{t['method']}</p>
        </div>"""
    ctx["tasks_html"] = tasks_html

    ex_html = ""
    for i, e in enumerate(plan["fitness"]["exercises"]):
        key = f"ex{i}"
        checked = "checked" if log["fitness"].get(key) else ""
        ex_html += f"""
        <div class="task">
          <label><input type="checkbox" data-cat="fitness" data-key="{key}" {checked}>
            <strong>{e['name']}</strong> · {e['sets']}组 × {e['reps']}</label>
        </div>"""
    ctx["exercises_html"] = f"""
        <p class="warmup">热身：{plan['fitness']['warm_up']} ｜ 整理：{plan['fitness']['cool_down']}</p>
        {ex_html}"""

    ctx["notes"] = log.get("notes", "")
    ctx["weight"] = log.get("weight", "")
    ctx["rating"] = log.get("rating", "")

    html = page_head(f"{plan['date']} 今日计划", "today")
    html += render_simple(MAIN_TODAY, ctx)
    html += page_foot()
    return html


MAIN_TODAY = """
<main class="container">
  <header class="today-head">
    <div>
      <h1>{{ date }} <span class="weekday">{{ weekday }}</span></h1>
      <p class="sub">饮食：{{ diet_goal }} ｜ 学习：{{ study_theme }} ｜ 健身：{{ fitness_session }}</p>
    </div>
    <button onclick="location.href='/generate?date={{ today_date }}'">重新生成今日计划</button>
  </header>

  <section class="grid">
    <div class="card">
      <h2>🍱 今日饮食</h2>
      <div class="target">目标：{{ diet_target_cals }} kcal / {{ diet_target_pro }}g 蛋白 ｜ 预计：{{ diet_est_cals }} kcal / {{ diet_est_pro }}g 蛋白</div>
      {{ meals_html }}
    </div>

    <div class="card">
      <h2>📚 今日学习</h2>
      <div class="target">主题：{{ study_theme }}（{{ study_goal }}）</div>
      {{ tasks_html }}
    </div>

    <div class="card">
      <h2>💪 今日健身</h2>
      <div class="target">{{ fitness_session }} · {{ fitness_type }} · 约{{ fitness_duration }}分钟</div>
      {{ exercises_html }}
    </div>

    <div class="card">
      <h2>🌙 今日提醒</h2>
      <ul class="remind">
        <li>饮水目标：{{ water }} L</li>
        <li>睡眠：{{ sleep }} 前睡 ｜ 起床：{{ wake }}</li>
        <li>学习复盘：21:30</li>
      </ul>
    </div>
  </section>

  <section class="card">
    <h2>📝 今日记录</h2>
    <label>体重（可选）<input type="text" id="weight" value="{{ weight }}" placeholder="kg"></label>
    <label>今日自评（1-10）<input type="text" id="rating" value="{{ rating }}" placeholder="8"></label>
    <label>今日感想<textarea id="notes" rows="3">{{ notes }}</textarea></label>
    <button onclick="saveLog()">保存记录</button>
    <span id="saveTip"></span>
  </section>
</main>

<script>
function saveLog(){
  var data = {
    weight: document.getElementById('weight').value,
    rating: document.getElementById('rating').value,
    notes: document.getElementById('notes').value,
    diet: {}, study: {}, fitness: {}
  };
  document.querySelectorAll('input[type=checkbox]').forEach(function(cb){
    data[cb.dataset.cat][cb.dataset.key] = cb.checked;
  });
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/log?date={{ today_date }}', true);
  xhr.setRequestHeader('Content-Type','application/json');
  xhr.onload = function(){ document.getElementById('saveTip').innerText = '已保存 ✓'; setTimeout(function(){document.getElementById('saveTip').innerText='';},2000); };
  xhr.send(JSON.stringify(data));
}
</script>
"""


def render_calendar():
    dates = list_plan_dates()
    rows = ""
    for fn in dates:
        d = fn.replace(".json", "")
        plan = load_plan(d)
        if not plan:
            continue
        # 完成率简单计算：检查日志
        log = load_log(d)
        checks = 0
        total = 0
        for cat in ["diet", "study", "fitness"]:
            for k, v in log.get(cat, {}).items():
                total += 1
                if v:
                    checks += 1
        rate = (checks * 100 // total) if total else 0
        rows += f"""
        <tr>
          <td><a href="/?date={d}">{d}</a></td>
          <td>{plan['weekday']}</td>
          <td>{plan['study']['theme']}</td>
          <td>{plan['fitness']['session']}</td>
          <td>{plan['diet']['summary']['estimated_calories']} kcal</td>
          <td><span class="rate rate-{rate//10*10}">{rate}%</span></td>
        </tr>"""
    html = page_head("日历 · 历史记录", "calendar")
    html += f"""
    <main class="container">
      <h1>📅 计划日历</h1>
      <table class="tbl">
        <thead><tr><th>日期</th><th>星期</th><th>学习主题</th><th>健身</th><th>饮食热量</th><th>完成率</th></tr></thead>
        <tbody>{rows if rows else '<tr><td colspan="6">还没有历史计划，先生成今天的吧。</td></tr>'}</tbody>
      </table>
    </main>"""
    html += page_foot()
    return html


def render_diet():
    dates = list_plan_dates()[:14]
    cards = ""
    for fn in dates:
        d = fn.replace(".json", "")
        plan = load_plan(d)
        if not plan:
            continue
        meals = "".join([f"<li><b>{m['meal']}</b> {m['dish']} <span class='meta'>{m['calories']}kcal/{m['protein_g']}g</span></li>" for m in plan['diet']['meals']])
        cards += f"""
        <div class="card">
          <h3>{d} {plan['weekday']}</h3>
          <ul class="meals">{meals}</ul>
          <p class="target">预计 {plan['diet']['summary']['estimated_calories']} kcal / {plan['diet']['summary']['estimated_protein_g']}g 蛋白</p>
        </div>"""
    html = page_head("饮食记录", "diet")
    html += f"""
    <main class="container">
      <h1>🍱 饮食记录</h1>
      <div class="grid grid3">{cards if cards else '<p>暂无饮食记录。</p>'}</div>
    </main>"""
    html += page_foot()
    return html


def render_study():
    dates = list_plan_dates()[:14]
    cards = ""
    for fn in dates:
        d = fn.replace(".json", "")
        plan = load_plan(d)
        if not plan:
            continue
        tasks = "".join([f"<li><b>{t['task']}</b>：{t['target']}</li>" for t in plan['study']['tasks']])
        cards += f"""
        <div class="card">
          <h3>{d} {plan['weekday']} · {plan['study']['theme']}</h3>
          <ul>{tasks}</ul>
        </div>"""
    html = page_head("学习记录", "study")
    html += f"""
    <main class="container">
      <h1>📚 学习记录</h1>
      <div class="grid grid3">{cards if cards else '<p>暂无学习记录。</p>'}</div>
    </main>"""
    html += page_foot()
    return html


def render_fitness():
    dates = list_plan_dates()[:14]
    cards = ""
    for fn in dates:
        d = fn.replace(".json", "")
        plan = load_plan(d)
        if not plan:
            continue
        ex = "".join([f"<li>{e['name']} {e['sets']}组×{e['reps']}</li>" for e in plan['fitness']['exercises']])
        cards += f"""
        <div class="card">
          <h3>{d} {plan['weekday']} · {plan['fitness']['session']}</h3>
          <ul>{ex}</ul>
          <p class="target">{plan['fitness']['type']} · 约{plan['fitness']['duration_minutes']}分钟</p>
        </div>"""
    html = page_head("健身记录", "fitness")
    html += f"""
    <main class="container">
      <h1>💪 健身记录</h1>
      <div class="grid grid3">{cards if cards else '<p>暂无健身记录。</p>'}</div>
    </main>"""
    html += page_foot()
    return html


def render_review():
    dates = list_plan_dates()[:7]
    rows = ""
    for fn in dates:
        d = fn.replace(".json", "")
        log = load_log(d)
        rows += f"""
        <tr>
          <td>{d}</td>
          <td>{log.get('weight','—')}</td>
          <td>{log.get('rating','—')}</td>
          <td>{log.get('notes','')}</td>
        </tr>"""
    html = page_head("复盘记录", "review")
    html += f"""
    <main class="container">
      <h1>🌙 复盘记录</h1>
      <table class="tbl">
        <thead><tr><th>日期</th><th>体重</th><th>自评</th><th>感想</th></tr></thead>
        <tbody>{rows if rows else '<tr><td colspan=4>暂无记录。</td></tr>'}</tbody>
      </table>
      <div class="card tip">
        <p>建议每周日做一次完整复盘：回顾本周计划完成率、饮食达标情况、学习进展，再调整下周目标。</p>
      </div>
    </main>"""
    html += page_foot()
    return html


# ---------------- HTTP 处理器 ----------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        qs = parse_qs(u.query)
        date = qs.get("date", [today_date()])[0]

        if path in ("/", "/today"):
            return self._send(200, render_today(date).encode("utf-8"))
        if path == "/calendar":
            return self._send(200, render_calendar().encode("utf-8"))
        if path == "/diet":
            return self._send(200, render_diet().encode("utf-8"))
        if path == "/study":
            return self._send(200, render_study().encode("utf-8"))
        if path == "/fitness":
            return self._send(200, render_fitness().encode("utf-8"))
        if path == "/review":
            return self._send(200, render_review().encode("utf-8"))
        if path == "/generate":
            ok, msg = run_generate(date)
            body = f"<meta charset='utf-8'><script>alert('{msg.replace(chr(10),' ')}');location.href='/?date={date}';</script>"
            return self._send(200, body.encode("utf-8"))
        if path.startswith("/static/"):
            fpath = os.path.join(BASE_DIR, path.lstrip("/"))
            if os.path.exists(fpath) and os.path.isfile(fpath):
                with open(fpath, "rb") as f:
                    data = f.read()
                ctype = "text/css" if path.endswith(".css") else "application/javascript" if path.endswith(".js") else "application/octet-stream"
                return self._send(200, data, ctype)
            return self._send(404, b"not found")
        self._send(404, b"not found")

    def do_POST(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        if u.path == "/api/log":
            date = qs.get("date", [today_date()])[0]
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            save_log(date, data)
            self._send(200, b'{"ok":true}', "application/json")
            return
        self._send(404, b"not found")


def main():
    ensure_dirs()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"==================================================")
    print(f"  个人学习生活平台已启动")
    print(f"  浏览器打开：http://{HOST}:{PORT}")
    print(f"  按 Ctrl+C 停止")
    print(f"==================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        server.shutdown()


if __name__ == "__main__":
    main()
