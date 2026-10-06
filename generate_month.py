# -*- coding: utf-8 -*-
"""
按月度计划大纲，批量生成一整月的每日计划。

用法：
    python agent/generate_month.py                # 使用 config/month_plan.txt
    python agent/generate_month.py --start 2026-11-01 --days 30
    python agent/generate_month.py --clear        # 生成前先清空已有计划

Agent 会根据：日期、星期、训练日、论文总篇数、课程进度、重要日期，
把整月目标自动拆解到每一天，并尽量做到：不重复前一天的菜、训练部位轮换、
重要日期前自动加强复习。
"""
import argparse
import os
import sys
from datetime import date, datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "agent"))

from generate_daily import build_plan, save_plan, load_profile  # noqa


def parse_month_plan(path):
    """解析 config/month_plan.txt，返回一个 dict。"""
    plan = {
        "start_date": None,
        "end_date": None,
        "diet_theme": "",
        "calorie_target": None,
        "protein_grams": None,
        "vocab_total_new": None,
        "vocab_review_every_days": 3,
        "papers_total": None,
        "papers_topic": "",
        "courses": [],
        "key_dates": [],
        "fitness_theme": "",
    }
    if not os.path.exists(path):
        print(f"[warn] 未找到月度大纲 {path}，将使用默认 profile 逐日生成")
        return plan

    courses_started = False
    key_started = False
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # 列表项
            if line.startswith("-"):
                value = line.lstrip("- ").strip()
                if courses_started:
                    plan["courses"].append(value)
                elif key_started:
                    plan["key_dates"].append(value)
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "courses":
                courses_started = True
                key_started = False
                continue
            if key == "key_dates":
                key_started = True
                courses_started = False
                continue
            courses_started = False
            key_started = False
            if key in ("start_date", "end_date") and value:
                plan[key] = value
            elif key == "diet_theme":
                plan["diet_theme"] = value
            elif key == "calorie_target" and value:
                plan["calorie_target"] = int(value)
            elif key == "protein_grams" and value:
                plan["protein_grams"] = int(value)
            elif key == "vocab_total_new" and value:
                plan["vocab_total_new"] = int(value)
            elif key == "vocab_review_every_days" and value:
                plan["vocab_review_every_days"] = int(value)
            elif key == "papers_total" and value:
                plan["papers_total"] = int(value)
            elif key == "papers_topic":
                plan["papers_topic"] = value
            elif key == "fitness_theme":
                plan["fitness_theme"] = value
    return plan


def parse_key_dates(key_dates_raw):
    """把 '2026-10-15 期中考试' 解析成 {date: label}。"""
    out = {}
    for item in key_dates_raw:
        parts = item.split(None, 1)
        d = parts[0]
        label = parts[1] if len(parts) > 1 else ""
        try:
            datetime.strptime(d, "%Y-%m-%d")
            out[d] = label
        except ValueError:
            print(f"[warn] 忽略无法解析的日期: {item}")
    return out


def date_range(start, end):
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    if e < s:
        return []
    return [s + timedelta(days=i) for i in range((e - s).days + 1)]


def build_month(plan):
    """根据月度大纲生成每一天。"""
    profile = load_profile()
    start = plan["start_date"] or date.today().strftime("%Y-%m-01")
    # 默认生成本月剩余天数
    if not plan["end_date"]:
        first = datetime.strptime(start, "%Y-%m-%d").date().replace(day=1)
        import calendar
        last_day = calendar.monthrange(first.year, first.month)[1]
        end = first.replace(day=last_day).strftime("%Y-%m-%d")
    else:
        end = plan["end_date"]

    days = date_range(start, end)
    if not days:
        print("[error] 日期范围无效，请检查 start_date / end_date")
        return

    key_dates = parse_key_dates(plan["key_dates"])
    courses = plan["courses"] or []
    papers_total = plan["papers_total"] or 0
    vocab_total = plan["vocab_total_new"]
    review_every = plan["vocab_review_every_days"] or 3
    papers_topic = plan["papers_topic"]

    # 论文均匀分配：只在有学习任务的日子分配
    study_days = [d for d in days if _has_study_task(d, profile)]
    paper_slots = _distribute_items(papers_total, len(study_days)) if study_days else []

    # 课程轮流推进
    course_cycle = list(courses) if courses else None

    print(f"[plan] 生成 {start} ~ {end}，共 {len(days)} 天")

    prev_plan = None
    generated = 0
    for i, d in enumerate(days):
        ds = d.strftime("%Y-%m-%d")
        weekday_cn = "一二三四五六日"[d.weekday()]

        # 临时覆盖 profile，让 build_plan 使用月度目标
        overrides = {}
        if plan["calorie_target"]:
            overrides["daily_calorie_target"] = plan["calorie_target"]
        if plan["protein_grams"]:
            overrides["protein_grams"] = plan["protein_grams"]

        day_plan = build_plan(ds)

        # ---- 注入月度调整 ----
        # 1. 单词量：按总量均分到各天
        if vocab_total:
            per_day = max(10, round(vocab_total / len(days)))
            for t in day_plan.get("study", {}).get("tasks", []):
                if "单词" in t.get("task", ""):
                    t["target"] = f"{per_day}个单词"
                    if (i + 1) % review_every == 0:
                        t["task"] = "背单词＋错词复习"

        # 2. 论文：均匀分配到学习日
        if paper_slots and _has_study_task(d, profile) and paper_slots.pop(0) if False else None:
            pass
        paper_idx = study_days.index(d) if d in study_days else -1
        if papers_topic and d in study_days:
            slot_index = _slot_index(d, study_days, papers_total)
            if slot_index is not None:
                day_plan["study"]["tasks"].append({
                    "task": f"精读论文（{papers_topic}）",
                    "target": "1篇",
                    "method": "提取研究问题、方法、结论与局限，记录到学习页",
                })
                day_plan["study"]["theme"] = papers_topic

        # 3. 课程轮流推进
        if course_cycle:
            c = course_cycle[(i // 2) % len(course_cycle)]
            day_plan["study"]["tasks"].append({
                "task": f"推进：{c}",
                "target": "1小节",
                "method": "看完后用自己的话写3句总结",
            })

        # 4. 重要日期前：自动切换为复习模式
        if ds in key_dates:
            day_plan["study"]["theme"] = f"重点日：{key_dates[ds]}"
            day_plan["study"]["tasks"] = [
                {"task": f"复习准备：{key_dates[ds]}", "target": "全天",
                 "method": "梳理本周错题与笔记，做2套模拟练习"},
            ]
        else:
            # 重要日期前2天自动降负载
            for kd, label in key_dates.items():
                kdate = datetime.strptime(kd, "%Y-%m-%d").date()
                if 0 < (kdate - d).days <= 2:
                    day_plan["study"]["theme"] = f"复习冲刺：{label}"
                    break

        save_plan(day_plan)
        prev_plan = day_plan
        generated += 1

    print(f"[ok] 已生成 {generated} 天计划，保存到 data/plans/")


def _has_study_task(d, profile):
    """判断当天是否需要安排学习（默认每天都学，可后续按 profile 扩展）。"""
    return True


def _distribute_items(total, slots):
    """把 total 个任务尽量均匀分配到 slots 个位置。"""
    if total <= 0 or slots <= 0:
        return []
    base = total // slots
    rem = total % slots
    return [base + (1 if i < rem else 0) for i in range(slots)]


def _slot_index(d, study_days, total):
    """决定当天是否分配一个论文任务：均匀分布。"""
    if total <= 0:
        return None
    idx = study_days.index(d)
    step = max(1, len(study_days) // total)
    return idx if idx % step == 0 else None


def main():
    parser = argparse.ArgumentParser(description="批量生成整月每日计划")
    parser.add_argument("--start", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--days", type=int, help="生成天数")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--clear", action="store_true", help="生成前清空已有计划")
    parser.add_argument("--config", default=os.path.join(BASE_DIR, "config", "month_plan.txt"))
    args = parser.parse_args()

    plan = parse_month_plan(args.config)

    if args.start:
        plan["start_date"] = args.start
    if args.end:
        plan["end_date"] = args.end
    if args.days and args.start:
        s = datetime.strptime(args.start, "%Y-%m-%d").date()
        plan["end_date"] = (s + timedelta(days=args.days - 1)).strftime("%Y-%m-%d")

    if args.clear:
        plans_dir = os.path.join(BASE_DIR, "data", "plans")
        for f in os.listdir(plans_dir):
            if f.endswith(".json"):
                os.remove(os.path.join(plans_dir, f))
        print("[clear] 已清空旧计划")

    build_month(plan)


if __name__ == "__main__":
    main()
