"""지난 리포트 모음 (2026-10-23 태형님)
   docs/archive/날짜-am.html, 날짜-pm.html 로 리포트를 따로 저장하고
   docs/archive/index.html 에 날짜 목록을 만든다. 같은 반나절에 여러 번이면 마지막 것.
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

    def cell(day: str, half: str) -> str:
        name = days[day].get(half)
        if not name:
            return '<td class="none">-</td>'
        return f'<td><a href="{name}">{_summary(os.path.join(ARCHIVE_DIR, name))}</a></td>'

    total = sum(len(v) for v in days.values())
    body, month = [], None
    for day in sorted(days, reverse=True):
        if day[:7] != month:
            if month:
                body.append("</table>")
            month = day[:7]
            body.append(f"<h2>{month[:4]}년 {int(month[5:])}월</h2>"
                        "<table><tr><th>날짜</th><th>오전</th><th>오후</th></tr>")
        d = datetime.strptime(day, "%Y-%m-%d")
        body.append(f"<tr><td class=\"d\">{d.month}/{d.day} ({WEEKDAYS[d.weekday()]})</td>"
                    f"{cell(day, 'am')}{cell(day, 'pm')}</tr>")
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
td.none{{color:#bbb}}
a{{color:#1a5fb4;text-decoration:none}}
</style></head><body>
<div class="top"><b>지난 바이오 키워드 리포트</b> &nbsp;|&nbsp; {len(days)}일 {total}개
 &nbsp;|&nbsp; <a href="../">오늘 리포트</a></div>
<div class="wrap">
{chr(10).join(body)}
<p style="color:#888;font-size:13px">오전 = 12시 전, 오후 = 12시 뒤 발송분. 같은 반나절에 여러 번 나갔으면 마지막 것만.
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
    build_index()
    return n


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if sys.argv[1:] == ["backfill"]:
        print(f"{backfill()}개 기록에서 꺼냄")
    else:
        save_current(); print(build_index())
