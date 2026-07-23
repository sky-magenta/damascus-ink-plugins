# -*- coding: utf-8 -*-
"""Синхронизация встроенных копий скиллов из их репозиториев.

Запуск (из корня умбреллы):  python scripts/sync_plugins.py
Клонирует каждый скилл-репозиторий (main, по https), копирует файлы плагина
в plugins/<имя>/ и записывает зафиксированный коммит в plugins/<имя>/.vendored-sha.
После запуска закоммитьте изменения — это и есть релиз новой версии скилла
в маркетплейсе.
"""
import json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOS = {
    "pravo-grammatika": "https://github.com/sky-magenta/pravo-grammatika.git",
    "pravo-logika": "https://github.com/sky-magenta/pravo-logika.git",
    "pravo-ritorika": "https://github.com/sky-magenta/pravo-ritorika.git",
}
# что входит в плагин (остальное — сайт/CI/тесты, плагину не нужны)
KEEP = ["SKILL.md", "references", "commands", ".claude-plugin",
        "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"]

def run(*cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"FAIL {' '.join(cmd)}: {r.stderr.strip()}")
    return r.stdout.strip()

def main():
    plugdir = os.path.join(ROOT, "plugins")
    os.makedirs(plugdir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, url in REPOS.items():
            src = os.path.join(tmp, name)
            run("git", "clone", "-q", "--depth", "1", url, src)
            sha = run("git", "rev-parse", "HEAD", cwd=src)
            dst = os.path.join(plugdir, name)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            os.makedirs(dst)
            for item in KEEP:
                s = os.path.join(src, item)
                if not os.path.exists(s):
                    continue
                d = os.path.join(dst, item)
                (shutil.copytree if os.path.isdir(s) else shutil.copyfile)(s, d)
            with open(os.path.join(dst, ".vendored-sha"), "w", encoding="utf-8") as f:
                f.write(sha + "\n")
            print(f"  {name}: {sha[:10]}")
    print("sync done — review `git status`, then commit")

if __name__ == "__main__":
    main()
