"""End-to-end UI test for Untrack Show, which also produces the README screenshots and demo video.

It drives the real jellyfin-web (with the plugin's script) from a Jellyfin server in headless Chromium, but answers
the Continue Watching / Next Up / item / image requests with three made-up shows. So it needs no particular library
content, never shows anything from your library, and changes nobody's watch history: the untrack request is answered
by the mock too.

Environment:
  JELLYFIN_URL         server address, e.g. http://127.0.0.1:8096
  JELLYFIN_TOKEN       a user session token (POST /Users/AuthenticateByName)
  JELLYFIN_USER_ID     that user's id
  JELLYFIN_SERVER_ID   the server id (returned by AuthenticateByName)
  JELLYFIN_DEVICE_ID   the DeviceId used when authenticating
  OUT_DIR              where screenshots and the video go (default: ./out)

Run it locally (pip install playwright && playwright install chromium; python3 test/ui_test.py) or in the
Playwright image:
  docker run --rm --network host --ipc=host --user "$(id -u):$(id -g)" -e HOME=/tmp -e OUT_DIR=/out \
      -e JELLYFIN_URL=... (and the other variables) -v "$PWD/test:/test:ro" -v "$PWD/out:/out" \
      mcr.microsoft.com/playwright/python:v1.64.1-noble \
      sh -c "pip install -q --user --break-system-packages playwright==1.64.1 && python3 /test/ui_test.py"

It exits non-zero if a check fails. Output: before.png, menu.png, mobile.png, after.png and video/*.webm (the README's
demo.gif is that video, trimmed and converted with ffmpeg).
"""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright

BASE = os.environ["JELLYFIN_URL"].rstrip("/")
SERVER_ID = os.environ["JELLYFIN_SERVER_ID"]
OUT = os.environ.get("OUT_DIR", "out")
os.makedirs(OUT, exist_ok=True)


def mock_id(*parts):
    return hashlib.md5(("untrack-demo:" + ":".join(map(str, parts))).encode()).hexdigest()


# ---- Made-up shows -------------------------------------------------------------------------------------------------

SHOWS = {
    "maple": {"name": "Maple Street", "year": 2014, "minutes": 22, "colors": ("#f6b04b", "#c2410c"), "genre": "Comedy"},
    "ward": {"name": "Ward Nine", "year": 2025, "minutes": 48, "colors": ("#2dd4bf", "#0e5a63"), "genre": "Drama"},
    "orbit": {"name": "Deep Orbit", "year": 2026, "minutes": 55, "colors": ("#a78bfa", "#312e81"), "genre": "Science Fiction"},
}
for key, show in SHOWS.items():
    show["key"] = key
    show["id"] = mock_id(key)

NOW = datetime.now(timezone.utc)

# Continue Watching, most recent first: a sitcom's random episodes from different seasons crowd the row.
RESUME = [
    ("maple", 5, 12, "The Garage Sale", 0.42),
    ("ward", 1, 7, "Night Rounds", 0.64),
    ("maple", 2, 5, "Game Night", 0.31),
    ("orbit", 1, 3, "Signal", 0.55),
    ("maple", 8, 3, "Moving Day", 0.22),
]
NEXT_UP = [
    ("maple", 3, 9, "Snow Day"),
    ("ward", 1, 8, "Code Blue"),
    ("orbit", 1, 4, "Drift"),
]

ITEMS = {}  # id -> item dto


def episode(key, season, number, title, progress=0.0, played_hours_ago=None):
    show = SHOWS[key]
    item_id = mock_id(key, season, number)
    ticks = show["minutes"] * 60 * 10_000_000
    user_data = {
        "PlaybackPositionTicks": int(ticks * progress), "PlayCount": 0, "IsFavorite": False, "Played": False,
        "Key": item_id, "ItemId": item_id,
    }
    if progress:
        user_data["PlayedPercentage"] = progress * 100
    if played_hours_ago is not None:
        user_data["LastPlayedDate"] = (NOW - timedelta(hours=played_hours_ago)).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
    item = {
        "Name": title, "ServerId": SERVER_ID, "Id": item_id, "Type": "Episode", "MediaType": "Video", "IsFolder": False,
        "LocationType": "FileSystem", "VideoType": "VideoFile", "CanDelete": False, "CanDownload": False,
        "IndexNumber": number, "ParentIndexNumber": season, "ProductionYear": show["year"],
        "RunTimeTicks": ticks, "SeriesName": show["name"], "SeriesId": show["id"],
        "SeasonId": mock_id(key, "season", season), "SeasonName": f"Season {season}",
        "ImageTags": {"Primary": "demo"}, "BackdropImageTags": [],
        "SeriesPrimaryImageTag": "demo", "ParentThumbItemId": show["id"], "ParentThumbImageTag": "demo",
        "ParentBackdropItemId": show["id"], "ParentBackdropImageTags": ["demo"],
        "UserData": user_data,
    }
    ITEMS[item_id] = item
    return item


def series(key):
    show = SHOWS[key]
    item = {
        "Name": show["name"], "ServerId": SERVER_ID, "Id": show["id"], "Type": "Series", "IsFolder": True,
        "LocationType": "FileSystem", "ProductionYear": show["year"], "Genres": [show["genre"]], "Status": "Continuing",
        "ImageTags": {"Primary": "demo", "Thumb": "demo"}, "BackdropImageTags": ["demo"],
        "UserData": {"PlaybackPositionTicks": 0, "PlayCount": 0, "IsFavorite": False, "Played": False,
                     "Key": show["id"], "ItemId": show["id"]},
    }
    ITEMS[show["id"]] = item
    return item


for key in SHOWS:
    series(key)
RESUME_ITEMS = [episode(k, s, n, t, p, played_hours_ago=i * 5 + 1) for i, (k, s, n, t, p) in enumerate(RESUME)]
NEXT_UP_ITEMS = [episode(k, s, n, t) for k, s, n, t in NEXT_UP]


def artwork(item_id, image_type):
    """A simple generated title card (SVG) for a made-up show."""
    item = ITEMS[item_id]
    show = SHOWS[next(k for k, s in SHOWS.items() if s["id"] in (item_id, item.get("SeriesId")))]
    poster = image_type == "Primary" and item["Type"] == "Series"
    w, h = (400, 600) if poster else (640, 360)
    c1, c2 = show["colors"]
    words = show["name"].upper().split()
    size = 46 if poster else 54
    lines = "".join(
        f'<text x="50%" y="{h / 2 + (i - (len(words) - 1) / 2) * size * 1.08:.0f}" text-anchor="middle" '
        f'dominant-baseline="middle" font-size="{size}" font-weight="800" letter-spacing="3">{word}</text>'
        for i, word in enumerate(words))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/>
<stop offset="1" stop-color="{c2}"/></linearGradient></defs>
<rect width="{w}" height="{h}" fill="url(#g)"/>
<circle cx="{w * .85:.0f}" cy="{h * .15:.0f}" r="{h * .55:.0f}" fill="#fff" opacity=".08"/>
<circle cx="{w * .1:.0f}" cy="{h * .95:.0f}" r="{h * .35:.0f}" fill="#000" opacity=".10"/>
<g fill="#fff" font-family="DejaVu Sans, Liberation Sans, Arial, sans-serif">{lines}</g>
</svg>'''


# ---- Request mocking ---------------------------------------------------------------------------------------------

state = {"untracked": set(), "deletes": []}
ID = r"([0-9a-f]{32})"


def visible(items):
    return [i for i in items if i["SeriesId"] not in state["untracked"]]


def json_reply(route, body, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


def handle(route):
    request = route.request
    path = request.url[len(BASE):].split("?")[0] if request.url.startswith(BASE) else None
    if path is None:
        return route.continue_()
    if path.startswith("/Branding/Css"):
        return route.fulfill(content_type="text/css", body="")  # stock look: no custom theme
    if path == "/Branding/Configuration":
        branding = route.fetch().json()
        branding["CustomCss"] = ""  # jellyfin-web also applies the custom CSS from here
        return json_reply(route, branding)  # stock look, no custom theme
    if path.startswith("/EditorsChoice/"):
        return route.fulfill(content_type="text/javascript", body="")  # other home-page plugins stay out of the shots
    if path in ("/System/Info", "/System/Info/Public"):
        info = route.fetch().json()
        info["ServerName"] = "Jellyfin"  # keep the real server name out of the screenshots
        return json_reply(route, info)
    if path.endswith("Items/Resume"):
        items = visible(RESUME_ITEMS)
        return json_reply(route, {"Items": items, "TotalRecordCount": len(items), "StartIndex": 0})
    if path.endswith("/Shows/NextUp"):
        items = visible(NEXT_UP_ITEMS)
        return json_reply(route, {"Items": items, "TotalRecordCount": len(items), "StartIndex": 0})
    if path.startswith("/DisplayPreferences/usersettings") and request.method == "GET":
        prefs = route.fetch().json()
        custom = prefs.setdefault("CustomPrefs", {})
        for n in range(10):
            custom[f"homesection{n}"] = {0: "resume", 1: "nextup"}.get(n, "none")
        return json_reply(route, prefs)
    m = re.match(rf"^/UserPlayedItems/{ID}$", path)
    if m and m.group(1) in ITEMS and request.method == "DELETE":
        state["untracked"].add(m.group(1))
        state["deletes"].append(m.group(1))
        return json_reply(route, ITEMS[m.group(1)]["UserData"])
    m = re.match(rf"^/Items/{ID}/Images/(\w+)", path)
    if m and m.group(1) in ITEMS:
        return route.fulfill(content_type="image/svg+xml", body=artwork(m.group(1), m.group(2)))
    m = re.match(rf"^(?:/Users/[0-9a-f]+)?/Items/{ID}$", path)
    if m and m.group(1) in ITEMS:
        return json_reply(route, ITEMS[m.group(1)])
    if any(i in path for i in ITEMS):
        print("unmocked request for a demo item:", request.method, path)
        return route.fulfill(status=404, body="")
    return route.continue_()


# ---- Browser helpers ---------------------------------------------------------------------------------------------

SESSION = json.dumps({"Servers": [{
    "ManualAddress": BASE, "manualAddressOnly": True, "Id": SERVER_ID, "Name": "Jellyfin",
    "LastConnectionMode": 2, "DateLastAccessed": int(time.time() * 1000),
    "UserId": os.environ["JELLYFIN_USER_ID"], "AccessToken": os.environ["JELLYFIN_TOKEN"],
}]})
LOGIN = (f"localStorage.setItem('jellyfin_credentials', {json.dumps(SESSION)});"
         f"localStorage.setItem('_deviceId2', {json.dumps(os.environ['JELLYFIN_DEVICE_ID'])});")

# A visible mouse pointer for the demo video (headless browsers don't draw one).
CURSOR = """window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M3 2v17l4.6-4.4 3.3 7.4 3.1-1.4-3.3-7.2H17z" '
    + 'fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  c.style.cssText = 'position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;transform:translate(-99px,-99px)';
  document.documentElement.appendChild(c);
  const move = e => { c.style.transform = 'translate(' + (e.clientX - 3) + 'px,' + (e.clientY - 2) + 'px)'; };
  document.addEventListener('mousemove', move, true);
  document.addEventListener('mousedown', e => {
    const r = document.createElement('div');
    r.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;width:34px;height:34px;border-radius:50%;'
      + 'background:rgba(255,255,255,.45);left:' + (e.clientX - 17) + 'px;top:' + (e.clientY - 17) + 'px;'
      + 'transition:transform .35s ease-out,opacity .35s ease-out';
    document.documentElement.appendChild(r);
    requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; });
    setTimeout(() => r.remove(), 450);
  }, true);
});"""


def new_page(browser, cursor=False, **context_args):
    context = browser.new_context(**context_args)
    context.add_init_script(LOGIN + (CURSOR if cursor else ""))
    context.route("**/*", handle)
    page = context.new_page()
    page.on("pageerror", lambda e: print("pageerror:", str(e)[:200]))
    return context, page


def open_home(page):
    state["untracked"].clear()
    page.goto(BASE + "/web/#/home")
    wait_for_rows(page)


def wait_for_rows(page):
    page.locator(".card", has_text="Ward Nine").first.wait_for(timeout=45000)
    page.wait_for_load_state("networkidle")
    page.wait_for_function("window.__untrackShowLoaded === true", timeout=15000)
    page.wait_for_timeout(800)  # let card images fade in


def glide(page, start, end, ms=600):
    """Move the mouse smoothly so the demo video shows the pointer travelling."""
    steps = max(1, ms // 16)
    for i in range(1, steps + 1):
        t = i / steps
        t = t * t * (3 - 2 * t)
        page.mouse.move(start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)
        page.wait_for_timeout(16)
    return end


def centre(locator):
    box = locator.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def maple_card(page):
    return page.locator(".card", has_text="Maple Street").first


def open_menu(page, card, pointer=None):
    """Open the card's ⋮ menu (hovering first, as a mouse user would) and wait for "Untrack show"."""
    if pointer:
        pointer = glide(page, pointer, centre(card), 700)
        page.wait_for_timeout(400)
    else:
        card.hover()
    button = card.locator('[data-action="menu"]').first
    if pointer:
        pointer = glide(page, pointer, centre(button), 350)
        page.wait_for_timeout(250)
        page.mouse.click(*pointer)
    else:
        button.click()
    option = page.locator('.actionSheet [data-id="untrackshow"]')
    option.wait_for(timeout=15000)
    page.wait_for_timeout(500)
    return option, pointer


def section_cards(page):
    return page.evaluate("""Array.from(document.querySelectorAll('.verticalSection')).map(s => [
        (s.querySelector('.sectionTitle') || {}).textContent,
        Array.from(s.querySelectorAll('.card')).map(c => (c.querySelector('.cardText') || {}).textContent)])""")


failures = []


def check(condition, message):
    print(("PASS " if condition else "FAIL ") + message)
    if not condition:
        failures.append(message)


with sync_playwright() as p:
    browser = p.chromium.launch()

    context, page = new_page(browser, viewport={"width": 1280, "height": 720}, device_scale_factor=2)
    open_home(page)
    page.screenshot(path=f"{OUT}/before.png")
    option, _ = open_menu(page, maple_card(page))
    items = page.locator(".actionSheet .actionSheetMenuItem").all_inner_texts()
    check("Untrack show" in items, f"menu offers Untrack show ({len(items)} items)")
    option.hover()
    page.wait_for_timeout(300)
    page.screenshot(path=f"{OUT}/menu.png")
    option.click()
    dialog = page.locator(".dialog", has_text="Untrack Maple Street?")
    dialog.wait_for(timeout=5000)
    check("marked unwatched" in dialog.inner_text(), "untrack asks for confirmation first")
    dialog.locator("button", has_text="Cancel").click()
    dialog.wait_for(state="detached", timeout=5000)
    page.wait_for_timeout(500)
    check(not state["deletes"], "cancel leaves the show tracked")
    context.close()

    # 2. Phone layout: cards have no ⋮ there; a long-press starts multi-select, whose bar has the ⋮.
    phone = {k: v for k, v in p.devices["Pixel 7"].items() if k != "default_browser_type"}
    context, page = new_page(browser, **phone)
    open_home(page)
    maple_card(page).click(button="right")  # what a long-press sends
    page.locator(".btnSelectionPanelOptions").tap()
    option = page.locator('.actionSheet [data-id="untrackshow"]')
    option.wait_for(timeout=15000)
    check(option.inner_text().strip() == "Untrack show", "phone: multi-select menu offers Untrack show")
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/mobile.png", clip={"x": 0, "y": 0, "width": phone["viewport"]["width"], "height": 600})
    page.evaluate("history.back()")  # menus close on "back"
    page.locator(".actionSheet").wait_for(state="detached", timeout=5000)
    page.locator(".card", has_text="Ward Nine").first.tap()  # in selection mode a tap toggles the card
    page.locator(".itemSelectionCount", has_text="2").wait_for(timeout=5000)
    page.locator(".btnSelectionPanelOptions").tap()
    option.wait_for(timeout=15000)
    check(option.inner_text().strip() == "Untrack 2 shows", "phone: two selected shows give Untrack 2 shows")
    page.wait_for_timeout(400)
    option.tap()
    page.locator(".dialog", has_text="Untrack 2 shows?").locator("button", has_text="Untrack").tap(timeout=5000)
    page.locator("text=Untracked 2 shows").wait_for(timeout=15000)
    check(sorted(state["deletes"]) == sorted([SHOWS["maple"]["id"], SHOWS["ward"]["id"]]),
          "phone: confirming untracks both selected shows")
    state["deletes"].clear()
    context.close()

    size = {"width": 1280, "height": 720}
    context, page = new_page(browser, cursor=True, viewport=size, record_video_dir=f"{OUT}/video", record_video_size=size)
    started = time.monotonic()
    open_home(page)
    ready = time.monotonic() - started
    pointer = glide(page, (1180, 650), (1100, 600), 200)
    page.wait_for_timeout(700)
    option, pointer = open_menu(page, maple_card(page), pointer)
    page.wait_for_timeout(500)
    pointer = glide(page, pointer, centre(option), 600)
    page.wait_for_timeout(450)
    page.mouse.click(*pointer)
    confirm = page.locator(".dialog button", has_text="Untrack")
    confirm.wait_for(timeout=5000)
    page.wait_for_timeout(1500)
    pointer = glide(page, pointer, centre(confirm), 500)
    page.wait_for_timeout(350)
    page.evaluate("window.__beforeUntrack = true")
    page.mouse.click(*pointer)
    page.wait_for_function("window.__beforeUntrack !== true", timeout=15000)
    page.locator("text=Untracked Maple Street").wait_for(timeout=10000)
    check(page.locator(".card", has_text="Ward Nine").count() > 0, "the untracked message shows once the page is back")
    wait_for_rows(page)
    page.mouse.move(1150, 640)
    page.wait_for_timeout(2500)
    check(state["deletes"] == [SHOWS["maple"]["id"]], "untrack sent DELETE /UserPlayedItems/{seriesId} for Maple Street")
    rows = section_cards(page)
    print("rows after untrack:", rows)
    check(not any("Maple Street" in c for _, cards in rows for c in cards), "Maple Street left Continue Watching and Next Up")
    check(sum("Ward Nine" in c for _, cards in rows for c in cards) == 2, "other shows stay")
    page.screenshot(path=f"{OUT}/after.png")
    video = page.video.path()
    context.close()
    print(f"video: {video} (rows ready at {ready:.1f}s)")

    # 4. The ⋮ on an episode's own page.
    context, page = new_page(browser, viewport={"width": 1280, "height": 720})
    state["untracked"].clear()
    page.goto(f"{BASE}/web/#/details?id={RESUME_ITEMS[0]['Id']}&serverId={SERVER_ID}")
    try:
        page.locator(".btnMoreCommands:visible").first.click(timeout=30000)
        option = page.locator('.actionSheet [data-id="untrackshow"]')
        option.wait_for(timeout=15000)
        check(option.inner_text().strip() == "Untrack show", "details page menu offers Untrack show")
    except Exception as err:
        page.screenshot(path=f"{OUT}/debug-details.png")
        check(False, f"details page menu offers Untrack show ({str(err).splitlines()[0]})")
    context.close()

    # Same view at 2x for the README.
    context, page = new_page(browser, viewport={"width": 1280, "height": 720}, device_scale_factor=2)
    state["untracked"].add(SHOWS["maple"]["id"])
    page.goto(BASE + "/web/#/home")
    wait_for_rows(page)
    page.screenshot(path=f"{OUT}/after.png")
    context.close()
    browser.close()

sys.exit(1 if failures else 0)
