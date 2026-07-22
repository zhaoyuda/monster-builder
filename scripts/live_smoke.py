#!/usr/bin/env python3
"""线上冒烟:对已部署的 demo 跑一遍真实浏览器检查(收工仪式,每次部署确认后必跑)。

用法:python3 scripts/live_smoke.py [--url https://zhaoyuda.github.io/monster-builder/play/index.html]
依赖:playwright(chromium)。
检查:页面可达、无 JS 错误、三个页签渲染、战役 4 关、引擎加载、瞬间挡打完一局出结算。
"""
import argparse
import sys

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://zhaoyuda.github.io/monster-builder/play/index.html"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    args = ap.parse_args()
    ok = True

    def check(name, cond, extra=""):
        nonlocal ok
        print(("✅" if cond else "💥 FAIL:"), name, extra)
        if not cond:
            ok = False

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 900, "height": 950})
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        resp = page.goto(args.url, wait_until="networkidle", timeout=30000)
        check("HTTP 200", resp is not None and resp.status == 200, resp and resp.status)
        page.wait_for_timeout(800)
        check("引擎加载", page.evaluate("typeof MonsterEngine") == "object")
        check("页签渲染", page.evaluate("!!($('tabCamp') && $('tabBuild') && $('tabFight'))"))
        check("战役 4 关", page.evaluate("$('lvCards').children.length") == 4)
        page.locator("#tabFight").click()
        page.evaluate("document.querySelector('#speedCtl button[data-s=\"0\"]').click()")
        page.locator("#startBtn").click()
        page.wait_for_timeout(1500)
        banner = page.evaluate("$('banner').textContent")
        check("瞬间挡打完一局出结算", any(s in banner for s in ("获胜", "击败", "平局")), banner[:40])
        check("全程无 JS 错误", not errs, errs[:3])
        b.close()

    print("\n🎉 线上冒烟通过" if ok else "\n💥 线上有问题,别收工")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
