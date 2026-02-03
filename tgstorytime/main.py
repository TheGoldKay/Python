from playwright.sync_api import sync_playwright
import os, json, time

# Where to save all downloaded EPUBs
DOWNLOAD_DIR = "V:\TG_STORY_TIME"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

OFFSET = 0 # start at frist page
STEP = 127 # each steap is a new web page
LIMIT = 6477 # a grand total of 51 steps + one last page with less than 127 novels
URL = "https://tgstorytime.com/browse.php?type=titles&offset={}" # listing all titles
NOVEL_LINK = "https://tgstorytime.com/{}" # link to each title given the id
HOME_PAGE = "https://tgstorytime.com/index.php" # log in first

"""
Rough loading order:

domcontentloaded -> HTML parsed, DOM tree ready. Scripts have run. Images/styles may still be loading.
load -> Page “fully” loaded: DOM, scripts, images, stylesheets, etc. Fires when the load event happens.
networkidle -> No network activity for ~500 ms (often never on busy sites).
"""

TITLES = dict[int, str] # the sid (story id) and the title

def get_novel_urls(page): # sid = story id
    #page.goto(URL.format(offset + STEP * 10), wait_until="load", timeout=60_000)
    #page.goto(URL.format(offset + STEP * 10), wait_until="networkidle", timeout=60_000)
    titles = []
    p = 1
    for offset in range(OFFSET, LIMIT + 1, STEP):
        page.goto(URL.format(offset), wait_until="domcontentloaded")
        #anchors = page.locator("a[href]")
        anchors = page.locator("div.title a[href^='viewstory.php?sid=']") 
        novels = []
        for i in range(anchors.count()):
            link = anchors.nth(i).get_attribute("href")
            #print(link, i)
            novels.append(NOVEL_LINK.format(link))
            #if link and link.startswith("viewstory.php?sid="):
                #link = link.split("=")[1]
                #sid = int(''.join(filter(str.isdigit, link)))
                #titles.add(sid)
        if p < 52: assert len(novels) == STEP, f"\nExpected {STEP} novels, got {len(novels)} -> OFFSET: {offset}\n"
        titles.extend(novels)
        print(f"Page Count: {p}")
        p += 1
        #download_all_epubs(page, novels)
    return titles

def login(page):
    page.goto(HOME_PAGE, wait_until="load")
    with open("credentials.json") as f:
        creds = json.load(f)

    user = creds["user"]
    password = creds["password"]

    page.wait_for_selector("#penname", state="visible")
    # <input type="text" class="textbox" name="penname" id="penname" size="15">
    page.fill("#penname", user)
    # <input type="password" class="textbox" name="password" id="password" size="15">
    #page.fill("#password", password)
    page.get_by_role("textbox", name="password").fill(password)
    # <input type="submit" class="button" name="submit" value="Go">
    page.get_by_role("button", name="Go").click()
    #page.click('input[type="submit"][value="Go"]')

def download_epub(page, novel_url, timeout=15_000): # timeout -> 1000 = 1s
    """Returns path on success, None if download failed (e.g. server error)."""
    try:
        # removed wait_until="domcontentloaded" because it's timing out constantly
        # now the script will wait till what's important appear
        page.goto(novel_url)
        base = page.locator('a[href*="epubversion/epubs/"][href$=".epub"]')
        epub_link = base.filter(has_text="Story").or_(base.filter(has_text="Download ePub"))
        epub_link.wait_for(state="visible", timeout=timeout)
        with page.expect_download(timeout=timeout) as download_info:
            epub_link.click()
        d = download_info.value
        path = os.path.join(DOWNLOAD_DIR, d.suggested_filename)
        d.save_as(path)
        return path
    except Exception as e:
        print(f" ---->>> FAILED (no download): {novel_url} - {e} <<<----")
        return None

def download_all_epubs(page, titles):
    failed = []
    success = 0
    for title in titles:
        #print(f"Downloading: {title}")
        path = download_epub(page, title)
        if not path:
            failed.append(title)
        else:
            success += 1
    print(f"\n\nTotal Novel Count: {success}")
    print(f"Failed Downloads: {len(failed)}\n")
    with open("failed.json", "w") as f:
        json.dump(failed, f)

def run():
    with sync_playwright() as p:
        # Launch browser (headless=True for invisible browser)
        browser = p.chromium.launch(headless=True)

        # Create a new context with a download directory
        context = browser.new_context(
            accept_downloads=True
        )
        page = context.new_page()
        login(page)
        start = time.time()
        titles = get_novel_urls(page)
        download_all_epubs(page, titles)
        end = time.time()
        total_min = (end - start)/60
        total_sec = int((total_min - int(total_min)) * 60)
        print(f"\n\n\nTime taken: {int(total_min)} minute and {total_sec} seconds")

        browser.close()


if __name__ == "__main__":
    run()
