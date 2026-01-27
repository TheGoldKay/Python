from playwright.sync_api import sync_playwright
import os

# Where to save all downloaded EPUBs
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

OFFSET = 127 # start at frist page
STEP = 127 # each steap is a new web page
LIMIT = 6477 # a grand total of 51 steps
URL = "https://tgstorytime.com/browse.php?type=titles&offset={}" # listing all titles

def get_page_url(offset):
    """Generate URL for a specific page by offset"""
    return URL.format(offset)

def iterate_pages():
    """Iterate through all pages from OFFSET to LIMIT"""
    for offset in range(OFFSET, LIMIT + 1, STEP):
        page_url = get_page_url(offset)
        yield page_url 

def get_story_ids(page):
    anchors = page.locator("a[href]")
    titles = set()
    for i in range(anchors.count()):
        link = anchors.nth(i).get_attribute("href")
        if link and link.startswith("viewstory.php?sid="):
            link = link.split("=")[1]
            sid = int(''.join(filter(str.isdigit, link)))
            titles.add(sid)
    return list(titles)

def run():
    with sync_playwright() as p:
        # Launch browser (headless=True for invisible browser)
        browser = p.chromium.launch(headless=True)

        # Create a new context with a download directory
        context = browser.new_context(
            accept_downloads=True
        )
        page = context.new_page()
        page.goto(get_page_url(OFFSET), wait_until="networkidle")
        ids = get_story_ids(page)
        print(f"Total Titles: {len(ids)}") # must me 127

        browser.close()


if __name__ == "__main__":
    run()
