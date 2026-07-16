#!/usr/bin/env python3
"""读取 summary.json 发送钉钉通知"""
import os, sys, json, requests
from pathlib import Path

SUMMARY_FILE = Path(__file__).parent / "summary.json"
PAGE_URL = "https://bailingsheng.github.io/BLS_vault/"


def send_dingtalk(webhook, data):
    counts = data["counts"]
    tops = data["tops"]

    lines = [f"📰 每日资讯日报 | {data['date']}", ""]

    cats = [
        ("ai", "🤖", "AI快讯"),
        ("stock", "📈", "股市行情"),
        ("exam", "🎓", "考研备考"),
    ]
    for key, emoji, label in cats:
        items = tops.get(key, [])
        lines.append(f"{emoji} {label} ({counts[key]}条)：")
        if items:
            for i, item in enumerate(items[:3], 1):
                lines.append(f"  {i}. {item['title']}")
        else:
            lines.append(f"  今日无重大资讯")
        lines.append("")

    lines.append(f"📰 完整日报 → {PAGE_URL}")

    payload = {"msgtype": "text", "text": {"content": "\n".join(lines)}}
    resp = requests.post(webhook, json=payload, timeout=15)
    result = resp.json()

    if result.get("errcode") == 0:
        print("✅ 钉钉发送成功")
    else:
        print(f"❌ 钉钉失败: {result}")
        sys.exit(1)


def main():
    webhook = os.environ.get("DINGTALK_WEBHOOK")
    if not webhook:
        print("ERROR: DINGTALK_WEBHOOK 未设置")
        sys.exit(1)
    if not SUMMARY_FILE.exists():
        print(f"ERROR: {SUMMARY_FILE} 不存在")
        sys.exit(1)

    data = json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
    send_dingtalk(webhook, data)


if __name__ == "__main__":
    main()
