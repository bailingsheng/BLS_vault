#!/usr/bin/env python3
"""
发送日报摘要到钉钉群机器人
环境变量: DINGTALK_WEBHOOK
"""
import os, sys, re, json, requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
TODAY = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
HTML_FILE = Path(__file__).parent / "index.html"
PAGE_URL = "https://bailingsheng.github.io/BLS_vault/"


def extract_tops(html):
    """从 HTML 中提取 Top 3 标题和描述"""
    tops = {"ai": [], "stock": [], "exam": []}

    # 匹配 Top 3 区域
    section_map = {"AI": "ai", "股市": "stock", "考研": "exam"}

    # 用简单的方式：找 summary-item 里的 stitle 和 sdesc
    items = re.findall(
        r'<div class="stitle">(.+?)</div>\s*<div class="sdesc">(.+?)</div>', html,
        re.DOTALL
    )

    # 前3条 → AI, 中间3条 → 股市, 后3条 → 考研
    for i, (title, desc) in enumerate(items[:9]):
        cat = "ai" if i < 3 else ("stock" if i < 6 else "exam")
        tops[cat].append((title.strip(), desc.strip()))

    # 统计各板块条数
    counts = {"ai": 0, "stock": 0, "exam": 0}
    for cat in counts:
        m = re.search(r'2025-01-01', html)  # dummy, won't match
    # 从入口卡片提取
    count_matches = re.findall(r'(\d+) 条今日资讯', html)
    if len(count_matches) >= 3:
        counts["ai"] = count_matches[0]
        counts["stock"] = count_matches[1]
        counts["exam"] = count_matches[2]

    return tops, counts


def send_dingtalk(webhook, tops, counts):
    """发送钉钉 markdown 消息"""
    lines = [
        f"## 📰 每日资讯日报 | {TODAY}",
        "",
        f"### 🤖 AI 快讯: {counts['ai']} 条 &nbsp;|&nbsp; 📈 股市: {counts['stock']} 条 &nbsp;|&nbsp; 🎓 考研: {counts['exam']} 条",
        "",
    ]

    emoji = {"ai": "🤖", "stock": "📈", "exam": "🎓"}
    for cat in ["ai", "stock", "exam"]:
        if tops[cat]:
            lines.append(f"**{emoji[cat]} {'AI快讯' if cat == 'ai' else ('股市行情' if cat == 'stock' else '考研备考')} Top 3:**")
            for i, (title, desc) in enumerate(tops[cat][:3], 1):
                lines.append(f"{i}. **{title}**：{desc}")
            lines.append("")

    lines.append(f"---")
    lines.append(f"📰 [查看完整日报]({PAGE_URL})")

    text = "\n".join(lines)

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"每日资讯日报 | {TODAY}",
            "text": text,
        },
    }

    resp = requests.post(webhook, json=payload, timeout=15)
    result = resp.json()
    if result.get("errcode") == 0:
        print("✅ 钉钉消息发送成功")
    else:
        print(f"❌ 钉钉发送失败: {result}")
        sys.exit(1)


def main():
    webhook = os.environ.get("DINGTALK_WEBHOOK")
    if not webhook:
        print("ERROR: DINGTALK_WEBHOOK 环境变量未设置")
        sys.exit(1)

    if not HTML_FILE.exists():
        print(f"ERROR: HTML 文件不存在: {HTML_FILE}")
        sys.exit(1)

    html = HTML_FILE.read_text(encoding="utf-8")
    tops, counts = extract_tops(html)
    send_dingtalk(webhook, tops, counts)


if __name__ == "__main__":
    main()
