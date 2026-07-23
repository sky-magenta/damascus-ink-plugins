# -*- coding: utf-8 -*-
"""Обновление закреплённых коммитов (sha) плагинов в marketplace.json.

Запуск (из корня умбреллы):  python scripts/sync_plugins.py
Для каждого плагина спрашивает у GitHub текущий HEAD ветки main
(git ls-remote — без клонирования) и, если репозиторий скилла ушёл вперёд,
обновляет поле source.sha. После запуска закоммитьте изменения — это и есть
релиз новой версии скилла в маркетплейсе. Автоматически то же самое делает
workflow .github/workflows/sync.yml (каждые 6 часов и по кнопке).
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, ".claude-plugin", "marketplace.json")

def head_of(url: str) -> str:
    r = subprocess.run(["git", "ls-remote", url, "refs/heads/main"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit(f"FAIL ls-remote {url}: {r.stderr.strip()}")
    return r.stdout.split()[0]

def main():
    m = json.load(open(MANIFEST, encoding="utf-8"))
    changed = False
    for pl in m["plugins"]:
        src = pl["source"]
        new = head_of(src["url"])
        old = src.get("sha", "")
        if new != old:
            src["sha"] = new
            changed = True
            print(f"  {pl['name']}: {old[:10] or '(none)'} -> {new[:10]}")
        else:
            print(f"  {pl['name']}: up to date ({new[:10]})")
    if changed:
        with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(m, ensure_ascii=False, indent=2) + "\n")
        print("pins updated — review `git status`, then commit")
    else:
        print("all pins up to date")

if __name__ == "__main__":
    main()
