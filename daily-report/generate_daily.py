#!/usr/bin/env python3
"""
每日资讯日报 — 自动生成脚本
每天北京时间 08:00 由 GitHub Actions 触发执行

依赖 API:
  - Tavily Search API  (搜索新闻)  → 免费 tier: 1000次/月
  - DeepSeek API       (筛选+生成)  → 约 ¥0.02/天
  - Jina Reader API    (抓取全文)   → 免费

环境变量 (在 GitHub Secrets 中配置):
  TAVILY_API_KEY
  DEEPSEEK_API_KEY
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── API Clients ──
try:
    from tavily import TavilyClient
except ImportError:
    print("请先安装: pip install tavily-python")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("请先安装: pip install openai")
    sys.exit(1)

import requests

# ── Config ──
BEIJING_TZ = timezone(timedelta(hours=8))
TODAY = datetime.now(BEIJING_TZ)
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
TODAY_STR = TODAY.strftime("%Y-%m-%d")
TODAY_WEEKDAY = WEEKDAYS[TODAY.weekday()]
YESTERDAY_STR = (TODAY - timedelta(days=1)).strftime("%Y-%m-%d")
OUTPUT_FILE = Path(__file__).parent / "index.html"

# ── Search Queries ──
SEARCH_QUERIES = {
    "ai_models": [
        "AI artificial intelligence news today",
        "OpenAI Anthropic Google DeepMind latest news",
        "大模型 AI 最新消息",
        "AI regulation policy July 2026",
        "AI芯片 GPU 最新动态",
    ],
    "ai_tools": [
        "AI coding tools Claude Code Cursor Copilot update",
        "GitHub trending AI open source project",
        "MCP protocol AI agent update 2026",
    ],
    "stock": [
        "A股 股市 行情 今日",
        "AI概念股 光模块 CPO 算力 2026",
        "美联储 央行 货币政策 人民币汇率",
        "NVIDIA stock AI chip news",
    ],
    "exam": [
        "考研 2027 招生 最新政策",
        "核工程 核技术 考研 招生简章",
        "考研 学硕 专硕 改革 2027",
    ],
}

# ── Prompt Templates ──
FILTER_PROMPT = """你是资深资讯编辑。从以下搜索结果中筛选过去24小时内最重要的资讯。

## 严格规则:
1. 只保留发布时间在 __YESTERDAY__ 到 __TODAY__ 之间的资讯（过去24小时）
2. 同一事件多个来源，只保留最权威的一个
3. 过滤掉: 娱乐八卦、营销软文、重复转载、无可靠来源的内容
4. AI相关优先: 新模型发布 > API/价格变化 > 商业合作 > 行业报告
5. 股市相关优先: 重大行情 > 政策变化 > 行业研报 > 个股公告
6. 考研相关优先: 官方政策 > 目标高校通知 > 择校信息 > 备考资料

## 输出格式 (严格JSON):
{
  "ai_major": [
    {"title": "...", "source_name": "...", "source_url": "...", "date": "...", "stars": 5, "summary": "2-4句话中文摘要", "insight": "一句话AI分析"}
  ],
  "ai_minor": [ ],
  "stock": [ ],
  "exam": [ ]
}

stars: 5=必须展示(新模型/政策/重大公告), 4=重点展示(行业报告/龙头企业), 3=简略展示
所有key必须用英文: ai_major, ai_minor, stock, exam
只返回JSON，不要任何其他文字。

## 搜索结果:
__SEARCH_RESULTS__
"""

# ── HTML Template ──
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日资讯日报 — {today}</title>
<style>
  :root {{
    --bg: #faf8f5; --card-bg: #ffffff; --border: #e8e5df;
    --text: #1e1e1e; --text-secondary: #555; --text-muted: #8c8c8c;
    --accent: #c75b39; --blue: #3b6fb6; --green: #4a7c59; --radius: 12px; --max-w: 880px;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: -apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC','PingFang SC',system-ui,sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.75; -webkit-font-smoothing: antialiased;
  }}
  .topbar {{
    position:sticky; top:0; z-index:100; background:rgba(250,248,245,0.92);
    backdrop-filter:blur(12px); border-bottom:1px solid var(--border);
    display:flex; align-items:center; justify-content:center; gap:4px; padding:0 24px; height:54px;
  }}
  .topbar a {{
    text-decoration:none; font-size:15px; font-weight:500; color:var(--text-muted);
    padding:8px 20px; border-radius:8px; transition:all 0.2s; cursor:pointer;
  }}
  .topbar a:hover {{ color:var(--text); background:rgba(0,0,0,0.04); }}
  .topbar a.active {{ color:var(--accent); background:rgba(199,91,57,0.08); font-weight:600; }}
  .topbar .brand {{ font-weight:700; font-size:16px; color:var(--text); margin-right:24px; letter-spacing:-0.3px; }}
  .container {{ max-width:var(--max-w); margin:0 auto; padding:0 28px; }}
  .page {{ display:none; padding-bottom:64px; }}
  .page.active {{ display:block; }}

  /* Home */
  .home-hero {{ text-align:center; padding:64px 0 48px; }}
  .home-hero .tag {{ display:inline-block; font-size:13px; font-weight:500; letter-spacing:0.8px; text-transform:uppercase; color:var(--accent); background:rgba(199,91,57,0.07); padding:5px 14px; border-radius:20px; margin-bottom:18px; }}
  .home-hero h1 {{ font-size:36px; font-weight:700; letter-spacing:-0.5px; }}
  .home-hero .sub {{ font-size:15px; color:var(--text-muted); margin-top:8px; }}
  .entry-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:20px; margin-bottom:56px; }}
  .entry-card {{
    background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius);
    padding:36px 28px 32px; cursor:pointer; transition:all 0.25s; text-decoration:none; color:inherit; display:block;
  }}
  .entry-card:hover {{ box-shadow:0 4px 20px rgba(0,0,0,0.06); transform:translateY(-2px); }}
  .entry-card .icon {{ font-size:36px; margin-bottom:16px; }}
  .entry-card h2 {{ font-size:20px; font-weight:700; margin-bottom:8px; }}
  .entry-card .desc {{ font-size:14px; color:var(--text-muted); line-height:1.6; }}
  .entry-card .count {{ display:inline-block; margin-top:16px; font-size:12px; font-weight:600; color:var(--accent); background:rgba(199,91,57,0.08); padding:3px 12px; border-radius:12px; }}

  /* Page Header */
  .page-header {{ text-align:center; padding:48px 0 36px; }}
  .page-header h1 {{ font-size:30px; font-weight:700; letter-spacing:-0.4px; }}
  .page-header .sub {{ font-size:14px; color:var(--text-muted); margin-top:6px; }}

  /* Card */
  .card {{
    background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius);
    padding:26px 30px; margin-bottom:14px; transition:box-shadow 0.2s;
  }}
  .card:hover {{ box-shadow:0 2px 14px rgba(0,0,0,0.04); }}
  .card-top {{ display:flex; align-items:flex-start; gap:14px; margin-bottom:10px; }}
  .card-top .stars {{ font-size:13px; letter-spacing:1.5px; flex-shrink:0; margin-top:3px; }}
  .stars.s5 {{ color:#c75b39; }} .stars.s4 {{ color:#c75b39; }} .stars.s3 {{ color:#b0a089; }}
  .card-title {{ font-size:17px; font-weight:650; line-height:1.5; flex:1; }}
  .card-meta {{ font-size:13px; color:var(--text-muted); margin-bottom:14px; display:flex; flex-wrap:wrap; gap:16px; align-items:center; }}
  .card-meta a {{ color:var(--blue); text-decoration:none; border-bottom:1px solid rgba(59,111,182,0.2); transition:border-color 0.15s; }}
  .card-meta a:hover {{ border-color:var(--blue); }}
  .card-body {{ font-size:15px; color:var(--text-secondary); line-height:1.8; }}
  .card-body a {{ color:var(--blue); text-decoration:none; border-bottom:1px solid rgba(59,111,182,0.2); }}
  .card-body a:hover {{ border-color:var(--blue); }}
  .card-insight {{ margin-top:16px; padding:14px 18px; background:#faf7f3; border-radius:8px; font-size:14px; color:#6b5e53; line-height:1.7; }}
  .card-insight::before {{ content:'分析 · '; font-weight:600; color:var(--accent); font-size:12px; letter-spacing:0.3px; }}
  .card-table {{ width:100%; border-collapse:collapse; font-size:14px; margin-top:6px; }}
  .card-table th {{ text-align:left; color:var(--text-muted); font-weight:500; font-size:12px; text-transform:uppercase; letter-spacing:0.4px; padding:8px 14px; border-bottom:1px solid var(--border); }}
  .card-table td {{ padding:10px 14px; border-bottom:1px solid #f0ede7; color:var(--text-secondary); line-height:1.6; }}
  .card-table tr:last-child td {{ border-bottom:none; }}
  .card-table .hl {{ color:var(--text); font-weight:600; }}

  /* Summary */
  .summary {{ margin:56px 0 40px; padding:36px 0 0; border-top:1px solid var(--border); }}
  .summary h2 {{ font-size:22px; font-weight:700; text-align:center; margin-bottom:28px; }}
  .summary-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:28px; }}
  .summary-col h3 {{ font-size:14px; font-weight:600; margin-bottom:16px; padding-bottom:10px; border-bottom:1px solid var(--border); }}
  .summary-item {{ padding:10px 0; border-bottom:1px solid #f0ede7; }}
  .summary-item:last-child {{ border-bottom:none; }}
  .summary-item .rank {{ font-size:26px; font-weight:700; color:#e0d8cc; line-height:1; }}
  .summary-item .stitle {{ font-size:14px; font-weight:600; margin:3px 0 2px; line-height:1.4; }}
  .summary-item .sdesc {{ font-size:12px; color:var(--text-muted); line-height:1.5; }}

  .back-link {{ text-align:center; margin-top:40px; }}
  .back-link a {{ color:var(--accent); text-decoration:none; font-size:14px; font-weight:500; }}

  .footer {{ text-align:center; padding:32px 0 52px; color:var(--text-muted); font-size:13px; border-top:1px solid var(--border); margin-top:40px; }}
  .footer p {{ margin-top:6px; }}

  .back-top {{ position:fixed; bottom:28px; right:28px; width:44px; height:44px; border-radius:50%; background:var(--card-bg); border:1px solid var(--border); color:var(--text-muted); font-size:18px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:all 0.2s; opacity:0; pointer-events:none; z-index:99; }}
  .back-top.show {{ opacity:1; pointer-events:auto; }}
  .back-top:hover {{ border-color:var(--accent); color:var(--accent); }}

  @media(max-width:720px) {{
    .entry-grid,.summary-grid {{ grid-template-columns:1fr; }}
    .card {{ padding:20px; }} .card-title {{ font-size:15px; }}
    .home-hero h1 {{ font-size:26px; }}
    .topbar a {{ font-size:13px; padding:6px 10px; }}
    .topbar .brand {{ font-size:14px; margin-right:8px; }}
  }}
  @media print {{
    body {{ background:#fff; }} .topbar,.back-top {{ display:none; }}
    .page {{ display:block!important; }} .card {{ box-shadow:none; break-inside:avoid; }}
  }}
</style>
</head>
<body>

<nav class="topbar">
  <span class="brand">Daily Report</span>
  <a class="active" onclick="switchPage('home')">首页</a>
  <a onclick="switchPage('ai')">AI 快讯</a>
  <a onclick="switchPage('stock')">股市</a>
  <a onclick="switchPage('exam')">考研</a>
</nav>

<div class="container">

<!-- ═══════ HOME ═══════ -->
<div class="page active" id="page-home">
  <div class="home-hero">
    <div class="tag">{today} · {weekday}</div>
    <h1>每日资讯日报</h1>
    <p class="sub">过去24小时 · AI 技术快讯 + 股市行情 + 考研备考</p>
  </div>
  <div class="entry-grid">
    <div class="entry-card" onclick="switchPage('ai')">
      <div class="icon">🤖</div><h2>AI 技术快讯</h2>
      <p class="desc">大模型动态、开源生态、开发工具、行业政策——只收录真正重要的变化。</p>
      <span class="count">{ai_major_count} 条今日资讯</span>
    </div>
    <div class="entry-card" onclick="switchPage('stock')">
      <div class="icon">📈</div><h2>股市行情简报</h2>
      <p class="desc">宏观市场、AI 产业链、热点板块轮动——聚焦影响今日市场的关键事件。</p>
      <span class="count">{stock_count} 条今日资讯</span>
    </div>
    <div class="entry-card" onclick="switchPage('exam')">
      <div class="icon">🎓</div><h2>考研备考专栏</h2>
      <p class="desc">核工程/核技术方向——招生政策、择校数据、每日备考要点。</p>
      <span class="count">{exam_count} 条今日资讯</span>
    </div>
  </div>
  <div class="summary">
    <h2>今日 Top 3 速览</h2>
    <div class="summary-grid">
      <div class="summary-col"><h3>🤖 AI</h3>{top3_ai}</div>
      <div class="summary-col"><h3>📈 股市</h3>{top3_stock}</div>
      <div class="summary-col"><h3>🎓 考研</h3>{top3_exam}</div>
    </div>
  </div>
</div>

<!-- ═══════ AI PAGE ═══════ -->
<div class="page" id="page-ai">
  <div class="page-header">
    <h1>🤖 AI 技术快讯</h1>
    <p class="sub">{yesterday} - {today} · 仅收录真正有价值的变化</p>
  </div>
  {ai_cards}
  <div class="back-link"><a onclick="switchPage('home')">← 返回首页</a></div>
</div>

<!-- ═══════ STOCK PAGE ═══════ -->
<div class="page" id="page-stock">
  <div class="page-header">
    <h1>📈 股市行情简报</h1>
    <p class="sub">{yesterday} - {today}</p>
  </div>
  {stock_cards}
  <div class="back-link"><a onclick="switchPage('home')">← 返回首页</a></div>
</div>

<!-- ═══════ EXAM PAGE ═══════ -->
<div class="page" id="page-exam">
  <div class="page-header">
    <h1>🎓 考研备考专栏</h1>
    <p class="sub">目标：核工程、核技术、材料科学、辐射探测及工科相关专业 · {yesterday} - {today}</p>
  </div>
  {exam_cards}
  <div class="back-link"><a onclick="switchPage('home')">← 返回首页</a></div>
</div>

</div>

<div class="footer">
  <p>📌 本报由 AI Agent 自动生成，仅供信息参考，不构成任何投资建议或考研决策依据。</p>
  <p>Generated by DeepSeek · {today} 08:00 CST · 仅收录过去 24 小时资讯</p>
</div>

<button class="back-top" id="backTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">↑</button>

<script>
function switchPage(n){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  var t=document.getElementById('page-'+n);if(t)t.classList.add('active');
  document.querySelectorAll('.topbar a').forEach(a=>a.classList.remove('active'));
  document.querySelectorAll('.topbar a').forEach(a=>{{if(a.textContent.includes({{'AI':'AI','stock':'股市','exam':'考研','home':'首页'}}[n]||n))a.classList.add('active');}});
  window.scrollTo({{top:0,behavior:'smooth'}});
  history.replaceState(null,'',n==='home'?'#':'#'+n);
}}
var h=window.location.hash.replace('#','');
if(h&&['ai','stock','exam'].includes(h))switchPage(h);
var bt=document.getElementById('backTop');
window.addEventListener('scroll',function(){{bt.classList.toggle('show',window.scrollY>500);}});
</script>
</body>
</html>"""


def make_stars(n):
    stars = "★" * n + "☆" * (5 - n)
    cls = "s5" if n >= 5 else ("s4" if n >= 4 else "s3")
    return f'<span class="stars {cls}">{stars}</span>'


def make_card(title, stars, source_html, date_str, body, insight=None):
    src = ""
    for s in source_html:
        src += f'<a href="{s["url"]}" target="_blank">{s["name"]}</a> · '
    src = src.rstrip(" · ")

    html = f"""<div class="card">
    <div class="card-top">{make_stars(stars)}<div class="card-title">{title}</div></div>
    <div class="card-meta">{src} <span>{date_str}</span></div>
    <div class="card-body">{body}</div>"""
    if insight:
        html += f'\n    <div class="card-insight">{insight}</div>'
    html += "\n  </div>"
    return html


def make_top3_item(rank, title, desc):
    return f"""<div class="summary-item">
        <div class="rank">{rank:02d}</div>
        <div class="stitle">{title}</div>
        <div class="sdesc">{desc}</div>
      </div>"""


# ── API Functions ──

def search_tavily(query: str, client: TavilyClient) -> list[dict]:
    """Search using Tavily API, return list of results with url, title, content snippet."""
    try:
        resp = client.search(query, search_depth="basic", max_results=5, include_domains=[])
        results = []
        for r in resp.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "source": r.get("url", "").split("/")[2] if r.get("url") else "",
            })
        return results
    except Exception as e:
        print(f"  [WARN] Tavily search failed for '{query[:50]}...': {type(e).__name__}: {e}")
        return []


def fetch_full_text(url: str) -> str:
    """Use Jina Reader to get full article text (free)."""
    try:
        reader_url = f"https://r.jina.ai/{url}"
        resp = requests.get(reader_url, headers={"Accept": "text/markdown"}, timeout=15)
        if resp.status_code == 200:
            text = resp.text
            return text[:3000]  # Limit to 3000 chars
        return ""
    except Exception:
        return ""


def call_deepseek(prompt: str, api_key: str, max_tokens: int = 4000) -> str:
    """Call DeepSeek API (OpenAI-compatible)."""
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model="deepseek-v4-flash",  # 2026年7月24日后 deepseek-chat 将废弃
        max_tokens=max_tokens,
        temperature=0.3,
        messages=[
            {"role": "system", "content": "你是一个专业的资讯分析助手。只返回要求的JSON格式，不做额外解释。"},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content


# ── Main Pipeline ──

def main():
    print(f"=== 每日资讯日报生成 ===")
    print(f"日期: {TODAY_STR}")
    print(f"北京时间: {TODAY.strftime('%H:%M')}")

    # Check API keys
    tavily_key = os.environ.get("TAVILY_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

    if not tavily_key:
        print("ERROR: TAVILY_API_KEY 环境变量未设置")
        sys.exit(1)
    if not deepseek_key:
        print("ERROR: DEEPSEEK_API_KEY 环境变量未设置")
        sys.exit(1)

    tavily = TavilyClient(api_key=tavily_key)

    # ── Step 1: Search ──
    print("\n[1/4] 搜索资讯...")
    all_results = {}
    all_flat = []

    for category, queries in SEARCH_QUERIES.items():
        print(f"  {category}: {len(queries)} 个查询")
        category_results = []
        for q in queries:
            results = search_tavily(q, tavily)
            category_results.extend(results)
            all_flat.extend(results)

        # Deduplicate by URL
        seen = set()
        unique = []
        for r in category_results:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)
        all_results[category] = unique
        print(f"    → {len(unique)} 条去重结果")

    total = sum(len(v) for v in all_results.values())
    print(f"  总计: {total} 条候选资讯")

    if total < 3:
        print("ERROR: 搜索结果太少，中止生成")
        sys.exit(1)

    # ── Step 2: Fetch full text for top results ──
    print("\n[2/4] 抓取全文...")
    # Only fetch top results to save time
    top_urls = list(set(r["url"] for r in all_flat[:15]))
    fetched_content = {}
    for i, url in enumerate(top_urls):
        print(f"  [{i+1}/{len(top_urls)}] {url[:60]}...")
        text = fetch_full_text(url)
        if text:
            fetched_content[url] = text

    # Enrich results with full text
    for r in all_flat:
        if r["url"] in fetched_content:
            r["full_text"] = fetched_content[r["url"]]
        else:
            r["full_text"] = r.get("content", "")

    # ── Step 3: DeepSeek filters & summarizes ──
    print("\n[3/4] DeepSeek 筛选与生成...")

    # Prepare search results for Claude (compact format)
    search_json = []
    for cat, results in all_results.items():
        for r in results[:10]:  # Limit per category
            search_json.append({
                "category": cat,
                "title": r["title"],
                "url": r["url"],
                "source": r["source"],
                "snippet": r.get("content", "")[:500],
                "full_text": r.get("full_text", "")[:1500],
            })

    filter_prompt = FILTER_PROMPT.replace("__YESTERDAY__", YESTERDAY_STR).replace("__TODAY__", TODAY_STR).replace("__SEARCH_RESULTS__", json.dumps(search_json, ensure_ascii=False, indent=2))

    try:
        resp_text = call_deepseek(filter_prompt, deepseek_key, max_tokens=8000)
        # Extract JSON from response (LLM might wrap in ```json)
        if "```json" in resp_text:
            resp_text = resp_text.split("```json")[1].split("```")[0]
        elif "```" in resp_text:
            resp_text = resp_text.split("```")[1].split("```")[0]
        data = json.loads(resp_text.strip())
    except Exception as e:
        print(f"  ERROR: DeepSeek 返回解析失败: {e}")
        try:
            print(f"  原始响应前500字符: {resp_text[:500]}...")
        except:
            print("  无法获取原始响应")
        sys.exit(1)

    # ── Step 4: Generate HTML ──
    print("\n[4/4] 生成 HTML...")

    def build_cards(articles):
        if not articles:
            return "<p style='color:var(--text-muted);text-align:center;padding:40px;'>今日无重大资讯</p>"
        cards = []
        for a in articles:
            source_html = [{"name": a.get("source_name", "来源"), "url": a.get("source_url", "#")}]
            cards.append(make_card(
                title=a["title"],
                stars=a.get("stars", 3),
                source_html=source_html,
                date_str=a.get("date", TODAY_STR),
                body=a.get("summary", ""),
                insight=a.get("insight"),
            ))
        return "\n".join(cards)

    def build_top3(articles, limit=3):
        top = sorted(articles, key=lambda x: x.get("stars", 0), reverse=True)[:limit]
        items = []
        for i, a in enumerate(top):
            items.append(make_top3_item(i + 1, a["title"][:30], a.get("insight", "")[:40]))
        return "\n".join(items)

    ai_major = data.get("ai_major", [])
    ai_minor = data.get("ai_minor", [])
    ai_all = ai_major + ai_minor

    stock_data = data.get("stock", [])
    exam_data = data.get("exam", [])

    ai_cards = build_cards(ai_major)
    if ai_minor:
        # Add minor items as a table
        table_rows = ""
        for a in ai_minor:
            src_url = a.get("source_url", "#")
            src_name = a.get("source_name", "来源")
            table_rows += f'<tr><td class="hl">{a["title"][:25]}</td><td>{a.get("summary","")} <a href="{src_url}" target="_blank">{src_name}</a> · {a.get("date","")}</td></tr>\n'
        ai_cards += f"""<div class="card">
    <div class="card-top">{make_stars(3)}<div class="card-title">其他动态</div></div>
    <table class="card-table"><tr><th style="width:100px">主题</th><th>动态</th></tr>{table_rows}</table>
  </div>"""

    stock_cards = build_cards(stock_data)
    exam_cards = build_cards(exam_data)

    html = HTML_TEMPLATE.format(
        today=TODAY_STR,
        weekday=TODAY_WEEKDAY,
        yesterday=YESTERDAY_STR,
        ai_major_count=len(ai_all),
        stock_count=len(stock_data),
        exam_count=len(exam_data),
        ai_cards=ai_cards,
        stock_cards=stock_cards,
        exam_cards=exam_cards,
        top3_ai=build_top3(ai_all),
        top3_stock=build_top3(stock_data),
        top3_exam=build_top3(exam_data),
    )

    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"  已写入: {OUTPUT_FILE}")
    print(f"  文件大小: {OUTPUT_FILE.stat().st_size:,} bytes")

    # 同时输出 JSON 摘要，供钉钉机器人使用
    summary = {
        "date": TODAY_STR,
        "counts": {"ai": len(ai_all), "stock": len(stock_data), "exam": len(exam_data)},
        "tops": {
            "ai": [{"title": a["title"][:50], "desc": a.get("insight", "")[:50]} for a in sorted(ai_all, key=lambda x: x.get("stars", 0), reverse=True)[:3]],
            "stock": [{"title": a["title"][:50], "desc": a.get("insight", "")[:50]} for a in sorted(stock_data, key=lambda x: x.get("stars", 0), reverse=True)[:3]],
            "exam": [{"title": a["title"][:50], "desc": a.get("insight", "")[:50]} for a in sorted(exam_data, key=lambda x: x.get("stars", 0), reverse=True)[:3]],
        },
    }
    (OUTPUT_FILE.parent / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 完成! ===")
    print(f"  AI 资讯: {len(ai_all)} 条")
    print(f"  股市资讯: {len(stock_data)} 条")
    print(f"  考研资讯: {len(exam_data)} 条")


if __name__ == "__main__":
    main()
