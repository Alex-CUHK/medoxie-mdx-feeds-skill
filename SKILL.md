# Medoxie MDX Feeds Browser Reader

Read the `MDX Feeds` section from `https://www.medoxie.com/` using browser automation instead of static HTML scraping.

Use this skill when you need to:
- read the latest posts in `MDX Feeds`
- extract author, handle, relative time, title, summary, and post links
- continue into individual posts when the site is rendered client-side
- explain to the user when the page is still loading or when manual login/confirmation is required

## Why this skill exists
Medoxie is a modern Next.js app and the homepage content may be rendered after JavaScript executes. Static tools like `requests` and `beautifulsoup4` can miss the actual feed content. This skill uses a real browser so it can wait for the rendered UI.

## Inputs
- optional target URL, default `https://www.medoxie.com/`
- optional maximum number of posts
- optional `--full` flag to open each post and fetch additional text
- optional `--json` flag for machine-readable output

## What to do
1. Open the Medoxie homepage in a browser context.
2. Wait for one of these signals:
   - the text `MDX Feeds`
   - post cards or `Read more` links
   - author handles like `@...`
3. If the page still shows only a loading shell, wait a bit longer and retry.
4. Extract visible cards from the `MDX Feeds` section.
5. If `--full` is enabled, open each discovered post link and extract the visible article text.
6. If the page requires authentication or another human action, return a clear status message for the user.

## User-facing statuses
Return one of these statuses when appropriate:
- `ready`: feed content is visible and extraction succeeded
- `loading`: Medoxie is still rendering the feed
- `needs_user_action`: the page is asking the user to sign in or confirm something
- `not_found`: the page loaded but the feed section could not be located
- `error`: browser or site error

## Example invocations
```bash
python3 scripts/read_mdx_feeds_browser.py
python3 scripts/read_mdx_feeds_browser.py --json
python3 scripts/read_mdx_feeds_browser.py --limit 5 --full --json
```

## Notes for OpenClaw
- Prefer this skill over static scraping for Medoxie feed reading.
- If the script returns `needs_user_action`, send the returned `user_message` back to the user.
- If the script returns `loading`, wait briefly and try again.
- If Playwright is missing, install it and the browser runtime first.
