from playwright.sync_api import sync_playwright
from pathlib import Path
import os, json, time


# Where to save all downloaded EPUBs
DOWNLOAD_DIR = "V:\TG_STORY_TIME_3rd_Run"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

OFFSET = 0 # start at frist page
STEP = 127 # each steap is a new web page
LIMIT = 6477 # a grand total of 51 steps + one last page with less than 127 novels
URL = "https://tgstorytime.com/browse.php?type=titles&offset={}" # listing all titles
NOVEL_LINK = "https://tgstorytime.com/{}" # link to each title given the id
HOME_PAGE = "https://tgstorytime.com/index.php" # log in first
DOWNLOAD_LOCATOR_TIMEOUT = 40_000
DOWNLOAD_EVENT_TIMEOUT = 60_000

"""
                                            PROJECT NOTES
Rough loading order:

domcontentloaded -> HTML parsed, DOM tree ready. Scripts have run. Images/styles may still be loading.
load -> Page “fully” loaded: DOM, scripts, images, stylesheets, etc. Fires when the load event happens.
networkidle -> No network activity for ~500 ms (often never on busy sites).

First Run: 04/02/2026 - TG Storytime has 6574 stories from 2006 authors

Total Novel Count (counted by the script): 6.329
Total Novel Count (listed on folder): 6.286
Failed Downloads Counter: 245
Time Taken (in minutes): 399

Note 1: 43 titles not accounted for as "failed downloads", investigation needed

Error 1: Timeout waiting for download event -> The click happens but no window pops up to save (page loads forever)
Error 2: Timeout waiting for selector of download to be visible -> No ePub available, manual scraping necessary 

Second Run: 06/02/2026 - TG Storytime has 6581 stories from 2007 authors

Total Novel Count (counted by the script): 6.338
Total Novel Count (listed on folder): 6.295
Failed Downloads Counter: 239

Note 1: Again the Total Novel Count differs from one counted by the script and the folder, yet the failed count is correct. 
Note 2: Unable to print time taken because of a bug when saving the errors to json, "TypeError: Object of type TimeoutError is not JSON serializable",
The difference still remains 43 though, thus a sign it's an internal error in my script

Second Run - Troubleshooting: 06/02/2026
Total Novel Count by script and folder: 2
Failed Downloads: 237
Time taken: 43 minutes

Note 1: Fed the failed_downloads.json as the novel list to download, only two successful downloads, considering
the 10 second constrain for locator and download event timeouts it went smoothly.
Note 2: This makes me think that the reason that the folder counter is lower than the script counter is due to 
duplications, that is, the same file name being saved more than once, and thus subscribling the older one, therefore
decreasing the folder counter, if I have to creat unique names to avoid such scenario, or check for duplications before
saving to disk. 
"""

ERRORS = []
DOWNLOAD_OK = []
COUNTER = 0

def find_empty_epubs(root_folder: str):
    """
    Just checking if there are any empty/blank files
    """
    root_path = Path(root_folder)


    print(f"\nScanning for empty .epub files under: {root_folder}\n")
    smallest = float('inf')
    smallest_name = ""
    for dirpath, _, filenames in os.walk(root_path):
        for filename in filenames:
            if filename.lower().endswith(".epub"):
                full_path = Path(dirpath) / filename
                try:
                    size = full_path.stat().st_size
                    if size < smallest:
                        smallest = size
                        smallest_name = filename
                except OSError as e:
                    print(f"Could not read {full_path}: {e}")
                    continue

                if size == 0:
                    print(filename)
    print(f"Smallest File: {smallest_name} - {smallest/1024:.2f} KB\n")

def get_novel_urls(page): # sid = story id
    titles = []
    p = 1
    for offset in range(OFFSET, LIMIT + 1, STEP):
        page.goto(URL.format(offset), wait_until="domcontentloaded")
        anchors = page.locator("div.title a[href^='viewstory.php?sid=']") 
        novels = []
        for i in range(anchors.count()):
            link = anchors.nth(i).get_attribute("href")
            novels.append(NOVEL_LINK.format(link))
        if p < 52: assert len(novels) == STEP, f"\nExpected {STEP} novels, got {len(novels)} -> OFFSET: {offset}\n"
        titles.extend(novels)
        print(f"Page Count: {p}")
        p += 1
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
    print("\nLogged In Successfully\n")

def download_epub(page, novel_url, timeout=15_000): # timeout -> 1000 = 1s
    """Returns path on success, None if download failed (e.g. server error)."""
    global COUNTER
    try:
        # removed wait_until="domcontentloaded" because it's timing out constantly
        # now the script will wait till what's important appear
        page.goto(novel_url)
        base = page.locator('a[href*="epubversion/epubs/"][href$=".epub"]')
        epub_link = base.filter(has_text="Story").or_(base.filter(has_text="Download ePub"))
        epub_link.wait_for(state="visible", timeout=DOWNLOAD_LOCATOR_TIMEOUT)
        with page.expect_download(timeout=DOWNLOAD_EVENT_TIMEOUT) as download_info:
            # .click() also has timeout argument, but it's a fast event, so there is no need to set a higher timeout
            epub_link.click() 
        d = download_info.value
        file_name = f"{COUNTER} {d.suggested_filename}"
        COUNTER = COUNTER + 1
        path = os.path.join(DOWNLOAD_DIR, file_name)
        d.save_as(path)
        return True
    except Exception as e:
        print(f"$$$$$$$$$ FAILED (no download): {novel_url} - {e} $$$$$$$$$")
        ERRORS.append(str(e))
        return False

def download_all_epubs(page, titles):
    failed = []
    success = 0
    for title in titles:
        successful_download = download_epub(page, title)
        if successful_download:
            success += 1
            DOWNLOAD_OK.append(title)
        else:
            failed.append(title)
    print(f"\n\nTotal Novel Count: {success}")
    print(f"Failed Downloads: {len(failed)}\n")
    with open("failed_downloads.json", "w") as f:
        json.dump(failed, f)
    with open("success.json", "w") as sc:
        json.dump(DOWNLOAD_OK, sc)
    with open("ERRORS.json", "w") as file:
        json.dump(ERRORS, file)

def manual_download(page, title):
    pass

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
        start = time.time()
        #titles = get_novel_urls(page)
        with open("failed_downloads.json", "r") as f:
            titles = json.load(f)
        download_all_epubs(page, titles)
        end = time.time()
        total_min = (end - start)/60
        print(f"\n\n\nTime taken: {int(total_min)} minutes")

        browser.close()


if __name__ == "__main__":
    print("\n----------------- START ----------------------")

    run()
    
    #find_empty_epubs("V:\TG_STORY_TIME_2nd_Run")
