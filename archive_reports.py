"""지난 리포트 모음 (2026-10-23 태형님)
   docs/archive/날짜-am.html, 날짜-pm.html 로 리포트를 따로 저장하고(원본)
   오전 + 오후를 합친 하루 페이지 docs/archive/날짜.html 과 날짜 목록 index.html 을 만든다.
   같은 반나절에 여러 번이면 마지막 것. 오늘 페이지에 ?d=지난날짜 로 들어오면 그날 하루 페이지로 넘김.
   python archive_reports.py backfill  → git 기록에서 지난 리포트 전부 꺼내 넣기
"""
import os, re, subprocess, sys
from datetime import datetime

ARCHIVE_DIR = "docs/archive"
WEEKDAYS = "월화수목금토일"


def _key(ts: datetime) -> str:
    return f"{ts:%Y-%m-%d}-{'am' if ts.hour < 12 else 'pm'}"


def save_report(html: str, ts: datetime) -> str:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    path = os.path.join(ARCHIVE_DIR, _key(ts) + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def save_current(ts: datetime | None = None) -> str:
    with open("docs/index.html", encoding="utf-8") as f:
        return save_report(f.read(), ts or datetime.now())


def _sent_time(soup) -> str:
    b = soup.select_one(".status-banner")
    m = re.search(r"(\d{1,2}:\d{2})", b.get_text()) if b else None
    return m.group(1) if m else ""


def _url(card) -> str:
    a = card.select_one(".card-footer a") or card.find("a", href=True)
    return a["href"] if a else str(card)[:300]


def _comp_cards(soup):
    box = soup.select_one("#competitor > div")
    return box, ([d for d in box.find_all("div", recursive=False) if "box-shadow" in d.get("style", "")]
                 if box else [])


def merge_day(day: str) -> str | None:
    """오전 + 오후 리포트를 하루 페이지 하나로. 오후 페이지를 바탕으로 오전에만 있던 기사를 더함."""
    from bs4 import BeautifulSoup
    parts = []
    for half in ("am", "pm"):
        p = os.path.join(ARCHIVE_DIR, f"{day}-{half}.html")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                parts.append((half, BeautifulSoup(f.read(), "html.parser")))
    if not parts:
        return None
    base = parts[-1][1]
    times = {half: _sent_time(s) for half, s in parts}
    if len(parts) == 2:
        other = parts[0][1]
        wrap = base.select_one(".wrap")
        have = {_url(c) for c in base.select(".wrap article.card")}
        for sec in other.select(".wrap section"):
            title = sec.select_one(".section-title")
            new = [c for c in sec.select("article.card") if _url(c) not in have]
            if not new or wrap is None:
                continue
            tgt = next((b for b in wrap.select("section")
                        if b.select_one(".section-title") and title
                        and b.select_one(".section-title").get_text(strip=True) == title.get_text(strip=True)), None)
            if tgt is None:
                tgt = base.new_tag("section")
                if title:
                    tgt.append(title.__copy__())
                wrap.append(tgt)
            for p in tgt.select(".no-articles"):
                p.decompose()
            for c in new:
                tgt.append(c.__copy__()); have.add(_url(c))
        bbox, bcards = _comp_cards(base)
        obox, ocards = _comp_cards(other)
        if obox is not None:
            if bbox is None:
                base.body.append(other.select_one("#competitor").__copy__())
            else:
                seen = {_url(c) for c in bcards}
                for c in ocards:
                    if _url(c) not in seen:
                        bbox.append(c.__copy__()); seen.add(_url(c))
    # 건수, 제목, 안내 줄 고치기
    n_kw = len(base.select(".wrap article.card"))
    n_comp = len(_comp_cards(base)[1])
    h1 = base.select_one("#competitor h1")
    if h1:
        h1.string = f"#경쟁동향 ({n_comp}건)"
    meta = base.select_one(".meta")
    if meta:
        meta.clear()
        meta.append(f"{day} 하루 모음 | 전체 {n_kw}건" + (f" + 경쟁동향 {n_comp}건" if n_comp else ""))
    if base.title:
        base.title.string = f"바이오 키워드 리포트 {day} 하루 모음"
    sent = " + ".join(f"{'오전' if h == 'am' else '오후'} {t}".strip() for h, t in times.items())
    banner = base.select_one(".status-banner")
    note = base.new_tag("div", attrs={"class": "status-banner status-fresh"})
    note.append(f"🗓 {day} 하루 모음 ({sent} 발송분{' 합침' if len(parts) == 2 else ''}) | ")
    back = base.new_tag("a", href="./"); back.string = "📚 지난 리포트 목록"
    note.append(back)
    if banner:
        banner.replace_with(note)
    elif base.body:
        base.body.insert(0, note)
    path = os.path.join(ARCHIVE_DIR, f"{day}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(base))
    return path


def add_redirect(days: list[str], today: str, page: str = "docs/index.html") -> None:
    """오늘 페이지에 ?d=(또는 ?v=)지난날짜 로 들어오면 그날 하루 페이지로 넘김 (예전 텔레그램, 메일 링크용)."""
    with open(page, encoding="utf-8") as f:
        html = f.read()
    html = re.sub(r"<script id=\"archive-redirect\">.*?</script>\n?", "", html, flags=re.S)
    js = ('<script id="archive-redirect">(function(){var q=new URLSearchParams(location.search);'
          'var d=(q.get("d")||q.get("v")||"").replace(/[^0-9]/g,"");if(d.length<8)return;'
          'var day=d.slice(0,4)+"-"+d.slice(4,6)+"-"+d.slice(6,8);'
          f'var days={days!r};if(day!=="{today}"&&days.indexOf(day)>=0)'
          'location.replace("archive/"+day+".html");})();</script>\n')
    html = html.replace("</body>", js + "</body>", 1) if "</body>" in html else html + js
    with open(page, "w", encoding="utf-8") as f:
        f.write(html)


def publish_today(ts: datetime | None = None) -> None:
    """발송 때 부름: 원본 저장, 그날 하루 페이지, 목록, 오늘 페이지 넘김 스크립트."""
    ts = ts or datetime.now()
    save_current(ts)
    merge_day(f"{ts:%Y-%m-%d}")
    build_index()
    add_redirect(_days(), f"{ts:%Y-%m-%d}")


def _days() -> list[str]:
    return sorted({m.group(1) for n in os.listdir(ARCHIVE_DIR)
                   if (m := re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(am|pm)\.html", n))})


def _summary(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        html = f.read()
    m = re.search(r'class="meta">.*?전체 (\d+)건(?: \+ 경쟁동향 (\d+)건)?', html)
    if not m:
        return "보기"
    return f"{m.group(1)}건" + (f" + 경쟁 {m.group(2)}" if m.group(2) else "")


def build_index() -> str:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    days: dict[str, dict[str, str]] = {}
    for name in os.listdir(ARCHIVE_DIR):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(am|pm)\.html", name)
        if m:
            days.setdefault(m.group(1), {})[m.group(2)] = name

    total = len(days)
    body, month = [], None
    for day in sorted(days, reverse=True):
        if day[:7] != month:
            if month:
                body.append("</table>")
            month = day[:7]
            body.append(f"<h2>{month[:4]}년 {int(month[5:])}월</h2>"
                        "<table><tr><th>날짜</th><th>기사</th><th>발송</th></tr>")
        d = datetime.strptime(day, "%Y-%m-%d")
        page = f"{day}.html"
        summ = _summary(os.path.join(ARCHIVE_DIR, page)) if os.path.exists(os.path.join(ARCHIVE_DIR, page)) else "보기"
        sent = " + ".join(h for h, k in (("오전", "am"), ("오후", "pm")) if k in days[day])
        body.append(f"<tr id=\"{day}\"><td class=\"d\"><a href=\"{page}\">{d.month}/{d.day} ({WEEKDAYS[d.weekday()]})</a></td>"
                    f"<td><a href=\"{page}\">{summ}</a></td><td class=\"s\">{sent}</td></tr>")
    if month:
        body.append("</table>")

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>지난 바이오 키워드 리포트</title>
<style>
body{{font-family:-apple-system,'Malgun Gothic',sans-serif;margin:0;background:#f4f6f9;color:#222}}
.top{{background:#1a3a5c;color:#fff;padding:14px 18px}}
.top a{{color:#fff}}
.wrap{{max-width:640px;margin:0 auto;padding:8px 14px 40px}}
h2{{font-size:17px;margin:22px 0 8px;color:#1a3a5c}}
table{{width:100%;border-collapse:collapse;background:#fff;font-size:15px}}
th,td{{border-bottom:1px solid #e3e7ee;padding:9px 8px;text-align:center}}
th{{background:#eef2f7;font-weight:600}}
td.d{{text-align:left;white-space:nowrap}}
td.s{{color:#888;font-size:13px}}
a{{color:#1a5fb4;text-decoration:none}}
</style></head><body>
<div class="top"><b>지난 바이오 키워드 리포트</b> &nbsp;|&nbsp; {total}일
 &nbsp;|&nbsp; <a href="../">오늘 리포트</a></div>
<div class="wrap">
{chr(10).join(body)}
<p style="color:#888;font-size:13px">날짜를 누르면 그날 오전 + 오후 발송분을 합친 하루 페이지가 열려요(겹치는 기사는 한 번만).
 마지막 갱신 {datetime.now():%Y-%m-%d %H:%M}</p>
</div></body></html>"""
    path = os.path.join(ARCHIVE_DIR, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def backfill() -> int:
    log = subprocess.run(["git", "log", "--reverse", "--format=%H %at", "--", "docs/index.html"],
                         capture_output=True, text=True, check=True).stdout.split()
    n = 0
    for sha, at in zip(log[0::2], log[1::2]):
        html = subprocess.run(["git", "show", f"{sha}:docs/index.html"],
                              capture_output=True, check=True).stdout.decode("utf-8", "replace")
        save_report(html, datetime.fromtimestamp(int(at)))
        n += 1
    rebuild_days()
    return n


def rebuild_days() -> int:
    for day in _days():
        merge_day(day)
    build_index()
    return len(_days())


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if sys.argv[1:] == ["backfill"]:
        print(f"{backfill()}개 기록에서 꺼냄")
    elif sys.argv[1:] == ["days"]:
        print(f"하루 페이지 {rebuild_days()}개")
    else:
        save_current(); print(build_index())
