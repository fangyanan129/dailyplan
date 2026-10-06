# -*- coding: utf-8 -*-
"""
把当前项目渲染成纯静态站点，输出到 public/。
用于部署到 GitHub Pages 等静态托管服务。

与本地 server.py 的区别：这里把每日计划预渲染成真正的 .html 文件，
不依赖服务器实时生成，因此可以在任何静态托管上运行。
"""
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANS_DIR = os.path.join(BASE_DIR, "data", "plans")
LOGS_DIR = os.path.join(BASE_DIR, "data", "logs")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

sys.path.insert(0, os.path.join(BASE_DIR, "agent"))
import server as s  # noqa


def ensure():
    os.makedirs(PUBLIC_DIR, exist_ok=True)


def copy_static():
    """复制 static 目录到 public/static。"""
    import shutil
    dst = os.path.join(PUBLIC_DIR, "static")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    if os.path.isdir(STATIC_DIR):
        shutil.copytree(STATIC_DIR, dst)


def list_plan_dates():
    if not os.path.isdir(PLANS_DIR):
        return []
    return sorted([f.replace(".json", "") for f in os.listdir(PLANS_DIR) if f.endswith(".json")])


def render_today_page(date_str=None):
    """今日页：index.html（默认今天）。"""
    if not date_str:
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
    plan = s.load_plan(date_str)
    if not plan:
        # 若当天无计划，生成一份
        from generate_daily import build_plan, save_plan
        plan = build_plan(date_str)
        save_plan(plan)
    html = s.render_today(date_str)
    path = os.path.join(PUBLIC_DIR, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def render_date_page(date_str):
    """为每一天生成一个静态 HTML。"""
    html = s.render_today(date_str)
    path = os.path.join(PUBLIC_DIR, date_str)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    return path


def render_list_page(route, title, renderer):
    html = renderer()
    path = os.path.join(PUBLIC_DIR, route)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ensure()
    dates = list_plan_dates()
    if not dates:
        from datetime import datetime
        from generate_daily import build_plan, save_plan
        today = datetime.now().strftime("%Y-%m-%d")
        save_plan(build_plan(today))
        dates = list_plan_dates()

    print(f"[build] 共 {len(dates)} 天的计划")

    # 首页 = 最新一天
    idx = os.path.join(PUBLIC_DIR, "index.html")
    with open(idx, "w", encoding="utf-8") as f:
        f.write(s.render_today(dates[0]))
    print(f"  index.html -> {dates[0]}")

    # 每一天一个页面
    for d in dates:
        render_date_page(d)
    print(f"  生成 {len(dates)} 个日期页面")

    # 列表页
    render_list_page("calendar", "日历", s.render_calendar)
    render_list_page("diet", "饮食", s.render_diet)
    render_list_page("study", "学习", s.render_study)
    render_list_page("fitness", "健身", s.render_fitness)
    render_list_page("review", "复盘", s.render_review)
    print("  生成列表页: calendar / diet / study / fitness / review")

    copy_static()
    print("[ok] 静态站点已输出到 public/")


if __name__ == "__main__":
    main()
