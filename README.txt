Medoxie MDX Feeds Browser Skill
===============================

This is the browser-automation replacement for the earlier static MDX Feeds skill.

Why the earlier skill failed
----------------------------
The earlier version used requests + BeautifulSoup. That approach only sees the initial HTML shell. Medoxie now behaves like a client-rendered Next.js app, so the real feed content may only appear after JavaScript runs in a browser.

What this version changes
-------------------------
- Uses Playwright with Chromium
- Waits for the rendered page instead of scraping raw HTML only
- Extracts feed cards from visible UI text
- Can return clear statuses for OpenClaw: ready / loading / needs_user_action / not_found / error
- Can optionally follow post links with --full

Installation
------------
1. Put this folder under your OpenClaw skills directory.
2. Install dependencies:

   pip install playwright
   playwright install chromium

Usage
-----
python3 scripts/read_mdx_feeds_browser.py
python3 scripts/read_mdx_feeds_browser.py --json
python3 scripts/read_mdx_feeds_browser.py --limit 5 --full --json

How OpenClaw should use the result
----------------------------------
- If status is ready: summarize or pass through the extracted items.
- If status is loading: wait briefly, then retry.
- If status is needs_user_action: send user_message back to the user.
- If status is not_found: tell the user the rendered feed could not be located.
- If status is error: inspect the debug field.

Recommended upgrade path
------------------------
If you later identify Medoxie's internal feed API or exact DOM structure, tighten the selectors in scripts/read_mdx_feeds_browser.py for even better extraction quality.
