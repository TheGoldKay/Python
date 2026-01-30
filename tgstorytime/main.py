from playwright.sync_api import sync_playwright
import os, json

# Where to save all downloaded EPUBs
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

OFFSET = 0 # start at frist page
STEP = 127 # each steap is a new web page
LIMIT = 6477 # a grand total of 51 steps
URL = "https://tgstorytime.com/browse.php?type=titles&offset={}" # listing all titles
NOVEL_LINK = "https://tgstorytime.com/{}" # link to each title given the id
HOME_PAGE = "https://tgstorytime.com/index.php" # log in first

"""
Rough loading order:

domcontentloaded -> HTML parsed, DOM tree ready. Scripts have run. Images/styles may still be loading.
load -> Page “fully” loaded: DOM, scripts, images, stylesheets, etc. Fires when the load event happens.
networkidle -> No network activity for ~500 ms (often never on busy sites).
"""

def pages():
    for offset in range(OFFSET, LIMIT + 1, STEP):
        yield URL.format(offset) 

def get_page_sids(page, offset=OFFSET): # sid = story id
    #page.goto(URL.format(offset + STEP * 10), wait_until="load", timeout=60_000)
    #page.goto(URL.format(offset + STEP * 10), wait_until="networkidle", timeout=60_000)
    page.goto(URL.format(offset + STEP * 20), wait_until="domcontentloaded")
    #anchors = page.locator("a[href]")
    anchors = page.locator("div.title a[href^='viewstory.php?sid=']") 
    titles = []
    for i in range(anchors.count()):
        link = anchors.nth(i).get_attribute("href")
        #print(link, i)
        titles.append(NOVEL_LINK.format(link))
        #if link and link.startswith("viewstory.php?sid="):
            #link = link.split("=")[1]
            #sid = int(''.join(filter(str.isdigit, link)))
            #titles.add(sid)
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

def download_epub(page, novel_url):
    page.goto(NOVEL_LINK.format(novel_url), wait_until="load")
    with page.expect_download() as download_info:
        page.locator('a[href*="epubversion/epubs/"][href$=".epub"]').filter(has_text="Story").click()
    d = download_info.value
    path = os.path.join(DOWNLOAD_DIR, d.suggested_filename)
    d.save_as(path)
    return path

def run():
    with sync_playwright() as p:
        # Launch browser (headless=True for invisible browser)
        browser = p.chromium.launch(headless=False)

        # Create a new context with a download directory
        context = browser.new_context(
            accept_downloads=True
        )
        page = context.new_page()
        login(page)
        #page.goto(URL.format(STEP * 22))
        titles = get_page_sids(page)
        print(f"Titles Count: {len(titles)}") #TODO: Creat test to check if it's return exactly 127 links (except for the last page)
        #path = download_epub(page, 7753)
        #print(f"Saved: {path}")
        #page.goto(get_page_url(OFFSET), wait_until="networkidle")
        #ids = get_story_ids(page)
        #print(f"Total Titles: {len(ids)}") # must me 127

        browser.close()


if __name__ == "__main__":
    run()
