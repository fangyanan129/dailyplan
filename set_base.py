# -*- coding: utf-8 -*-
"""
设置网站基础路径，用于 GitHub Pages 子路径部署。
本地使用时可忽略；CI 中会调用：python scripts/set_base.py <repo-name>
"""
import sys
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD = os.path.join(BASE_DIR, "templates", "head.html")


def set_base(repo_name):
    if not os.path.exists(HEAD):
        print("[skip] 未找到 templates/head.html")
        return
    with open(HEAD, "r", encoding="utf-8") as f:
        html = f.read()

    # 在 <head> 中插入/更新 <base href="/repo_name/">
    base_tag = f'<base href="/{repo_name}/">'
    if re.search(r'<base\s+href="[^"]*">', html):
        html = re.sub(r'<base\s+href="[^"]*">', base_tag, html)
    else:
        html = html.replace("<head>", f"<head>\n{base_tag}")

    # 把 /static/... 改为 /repo_name/static/...
    html = re.sub(r'(href|src)="/static/', rf'\1="/{repo_name}/static/', html)

    with open(HEAD, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ok] base href 已设为 /{repo_name}/")


def reset_base():
    """本地开发时恢复为根路径（可选）。"""
    if not os.path.exists(HEAD):
        return
    with open(HEAD, "r", encoding="utf-8") as f:
        html = f.read()
    html = re.sub(r'<base\s+href="[^"]*">\n?', "", html)
    html = re.sub(r'(href|src)="/[^/]+/static/', r'\1="/static/', html)
    with open(HEAD, "w", encoding="utf-8") as f:
        f.write(html)
    print("[ok] 已恢复本地路径")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_base()
    elif len(sys.argv) > 1:
        set_base(sys.argv[1])
    else:
        print("用法: python set_base.py <repo_name>  |  python set_base.py --reset")
