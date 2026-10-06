# -*- coding: utf-8 -*-
"""
每日计划 Agent
读取 config/profile.json 与个人历史记录，根据日期与星期生成当天的
饮食 / 学习 / 健身计划，输出为 data/plans/YYYY-MM-DD.json。

只使用 Python 标准库，无需安装任何第三方包。
"""
import json
import os
import random
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "profile.json")
PLANS_DIR = os.path.join(BASE_DIR, "data", "plans")

WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# ---------- 素材库：可按个人口味增删 ----------
BREAKFAST_POOL = [
    {"dish": "无糖豆浆 + 水煮蛋2个 + 全麦面包1片", "calories": 420, "protein_g": 30},
    {"dish": "原味希腊酸奶 + 燕麦 + 蓝莓 + 水煮蛋1个", "calories": 400, "protein_g": 32},
    {"dish": "牛奶 + 鸡胸肉全麦三明治 + 水煮蛋1个", "calories": 460, "protein_g": 36},
    {"dish": "小米南瓜粥 + 水煮蛋2个 + 凉拌黄瓜", "calories": 390, "protein_g": 26},
    {"dish": "无糖豆浆 + 紫薯 + 水煮蛋2个", "calories": 410, "protein_g": 28},
    {"dish": "燕麦牛奶 + 水煮蛋2个 + 一小把坚果", "calories": 430, "protein_g": 30},
]
LUNCH_POOL = [
    {"dish": "香煎鸡胸肉 + 糙米饭 + 清炒西兰花", "calories": 560, "protein_g": 45},
    {"dish": "清蒸鱼 + 杂粮饭 + 蒜蓉菠菜", "calories": 540, "protein_g": 42},
    {"dish": "番茄牛腩 + 糙米饭 + 凉拌海带丝", "calories": 600, "protein_g": 40},
    {"dish": "虾仁滑蛋 + 杂粮饭 + 清炒芦笋", "calories": 530, "protein_g": 44},
    {"dish": "烤鸡腿（去皮）+ 糙米饭 + 清炒小白菜", "calories": 570, "protein_g": 43},
]
DINNER_POOL = [
    {"dish": "白灼虾 + 蒸南瓜 + 凉拌木耳", "calories": 420, "protein_g": 38},
    {"dish": "豆腐炖鱼片 + 蒸红薯 + 蒜蓉生菜", "calories": 400, "protein_g": 35},
    {"dish": "鸡胸肉蔬菜沙拉 + 玉米1根", "calories": 390, "protein_g": 36},
    {"dish": "清蒸鲈鱼 + 蒸山药 + 清炒油麦菜", "calories": 410, "protein_g": 37},
]
SNACK_POOL = [
    {"dish": "无糖酸奶 + 一小把原味坚果", "calories": 180, "protein_g": 12},
    {"dish": "水煮蛋1个 + 半个苹果", "calories": 150, "protein_g": 10},
    {"dish": "低脂牛奶一杯 + 小番茄", "calories": 160, "protein_g": 11},
]

# 训练部位周期，按训练日顺序轮换
WORKOUT_CYCLE = [
    {"day": "上肢推类", "exercises": [
        {"name": "哑铃卧推", "sets": 4, "reps": "10-12次"},
        {"name": "哑铃肩推", "sets": 3, "reps": "10-12次"},
        {"name": "俯卧撑", "sets": 3, "reps": "12-15次"},
        {"name": "绳索下压", "sets": 3, "reps": "12次"},
    ]},
    {"day": "下肢与核心", "exercises": [
        {"name": "哑铃深蹲", "sets": 4, "reps": "10-12次"},
        {"name": "哑铃罗马尼亚硬拉", "sets": 3, "reps": "10-12次"},
        {"name": "弹力带臀桥", "sets": 3, "reps": "15次"},
        {"name": "平板支撑", "sets": 3, "reps": "30-45秒"},
    ]},
    {"day": "上肢拉类与背", "exercises": [
        {"name": "哑铃划船", "sets": 4, "reps": "10-12次"},
        {"name": "弹力带高位下拉", "sets": 3, "reps": "10-12次"},
        {"name": "哑铃弯举", "sets": 3, "reps": "12次"},
        {"name": "面拉", "sets": 3, "reps": "15次"},
    ]},
    {"day": "全身循环 + 有氧", "exercises": [
        {"name": "哑铃深蹲推举", "sets": 3, "reps": "10次"},
        {"name": "哑铃弓步走", "sets": 3, "reps": "每侧10次"},
        {"name": "跑步机快走/慢跑", "sets": 1, "reps": "20分钟"},
        {"name": "登山跑", "sets": 3, "reps": "30秒"},
    ]},
]
REST_DAY_ACTIVITY = {"name": "休息日：散步30分钟 + 全身拉伸", "sets": 1, "reps": "约30分钟"}


def load_profile():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_recent_plans(days=3):
    """读取最近几天的计划，用于轮换食材、避免重复。"""
    recent = []
    today = datetime.now()
    for i in range(1, days + 1):
        d = today - timedelta(days=i)
        path = os.path.join(PLANS_DIR, d.strftime("%Y-%m-%d") + ".json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    recent.append(json.load(f))
            except Exception:
                pass
    return recent


def build_diet(profile, recent):
    diet_cfg = profile["diet"]
    target_cals = diet_cfg["daily_calories"]
    target_pro = diet_cfg["daily_protein_g"]

    recent_dishes = set()
    for p in recent:
        for m in p.get("diet", {}).get("meals", []):
            recent_dishes.add(m.get("dish", ""))

    def pick(pool):
        for _ in range(20):
            item = random.choice(pool)
            if item["dish"] not in recent_dishes:
                return item
        return random.choice(pool)

    meals = []
    b = pick(BREAKFAST_POOL)
    meals.append({"meal": "早餐", **b})
    l = pick(LUNCH_POOL)
    meals.append({"meal": "午餐", **l})
    d = pick(DINNER_POOL)
    meals.append({"meal": "晚餐", **d})
    total_cals = b["calories"] + l["calories"] + d["calories"]
    total_pro = b["protein_g"] + l["protein_g"] + d["protein_g"]

    if diet_cfg.get("snack"):
        s = pick(SNACK_POOL)
        meals.append({"meal": "加餐", **s})
        total_cals += s["calories"]
        total_pro += s["protein_g"]

    return {
        "goal": diet_cfg["goal"],
        "target": {
            "calories": target_cals,
            "protein_g": target_pro,
            "note": "控制油盐，优先清淡烹饪（蒸、煮、炖、烤）"
        },
        "meals": meals,
        "summary": {
            "estimated_calories": total_cals,
            "estimated_protein_g": total_pro,
            "calories_diff": total_cals - target_cals,
            "protein_diff": total_pro - target_pro
        },
    }


def build_study(profile, weekday_cn):
    study_cfg = profile["study"]
    theme = study_cfg["weekly_themes"].get(weekday_cn, "综合学习")
    vocab = study_cfg["vocab_per_day"]

    tasks = [
        {"task": "背诵单词", "target": f"{vocab}个单词",
         "method": "新词记忆 → 中英文抽测 → 睡前快速回顾"},
    ]
    if "精读" in theme:
        tasks.append({"task": "论文精读", "target": "1篇",
                      "method": "提取研究问题、方法、结论、局限，并做批注"})
    elif "泛读" in theme:
        tasks.append({"task": "文献泛读", "target": "2-3篇摘要/引言",
                      "method": "快速判断相关性与可借鉴之处"})
    elif "课程" in theme:
        tasks.append({"task": "课程学习", "target": "1个章节",
                      "method": f"结合课程 {study_cfg['current_courses'][0]}，边学边做笔记"})
    elif "复习" in theme or "错题" in theme:
        tasks.append({"task": "错题/笔记复习", "target": "1个主题",
                      "method": "回顾本周错题，整理知识框架"})
    elif "输出" in theme:
        tasks.append({"task": "写作输出", "target": "200-300字小结",
                      "method": "用自己的话复述今日所学"})
    elif "复盘" in theme or "计划" in theme:
        tasks.append({"task": "周复盘与下周计划", "target": "1次",
                      "method": "回顾本周完成率，调整下周任务量"})
    else:
        tasks.append({"task": "课程学习", "target": "1个主题",
                      "method": "按当前进度推进"})

    return {
        "theme": theme,
        "goal": study_cfg["goal"],
        "tasks": tasks,
        "courses": study_cfg["current_courses"],
    }


def build_fitness(profile, weekday_cn, today_dt):
    fit_cfg = profile["fitness"]
    if weekday_cn in fit_cfg["workout_days"]:
        # 按训练日顺序分配周期
        idx = fit_cfg["workout_days"].index(weekday_cn)
        cycle = WORKOUT_CYCLE[idx % len(WORKOUT_CYCLE)]
        session = {
            "session": cycle["day"],
            "type": "正式训练",
            "duration_minutes": fit_cfg["duration_minutes"],
            "warm_up": "5分钟关节活动与动态拉伸",
            "exercises": cycle["exercises"],
            "cool_down": "5分钟静态拉伸",
        }
    else:
        session = {
            "session": "休息与恢复",
            "type": "低强度活动",
            "duration_minutes": 30,
            "warm_up": "无需专门热身",
            "exercises": [REST_DAY_ACTIVITY],
            "cool_down": "10分钟全身拉伸",
        }
    session["goal"] = fit_cfg["goal"]
    return session


def build_plan(date_str=None):
    now = datetime.now()
    if date_str:
        now = datetime.strptime(date_str, "%Y-%m-%d")
    weekday_cn = WEEKDAYS_CN[now.weekday()]
    profile = load_profile()
    recent = load_recent_plans()

    plan = {
        "date": now.strftime("%Y-%m-%d"),
        "weekday": weekday_cn,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "diet": build_diet(profile, recent),
        "study": build_study(profile, weekday_cn),
        "fitness": build_fitness(profile, weekday_cn, now),
        "review": {
            "study_review_time": "21:30",
            "water_target_liters": profile["lifestyle"]["water_liters"],
            "sleep_target": profile["lifestyle"]["sleep_target"],
            "wake_target": profile["lifestyle"]["wake_target"],
        },
    }
    return plan


def save_plan(plan):
    os.makedirs(PLANS_DIR, exist_ok=True)
    path = os.path.join(PLANS_DIR, plan["date"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    return path


def main():
    plan = build_plan()
    path = save_plan(plan)
    print(f"[OK] 已生成 {plan['date']}（{plan['weekday']}）的计划：{path}")
    print(f"     饮食：{plan['diet']['summary']['estimated_calories']} kcal / "
          f"目标 {plan['diet']['target']['calories']} kcal，"
          f"蛋白 {plan['diet']['summary']['estimated_protein_g']}g")
    print(f"     学习主题：{plan['study']['theme']}")
    print(f"     健身：{plan['fitness']['session']}（{plan['fitness']['type']}）")


if __name__ == "__main__":
    main()
