from playwright.sync_api import sync_playwright
from ebooklib import epub
from pathlib import Path
import os
import json
import time


# Where to save all downloaded EPUBs
DOWNLOAD_DIR = "V:\TG_FINAL"
TG_MANUAL_DOWNLOAD = DOWNLOAD_DIR
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

OFFSET = 0  # start at frist page
STEP = 127  # each steap is a new web page
LIMIT = 6477  # a grand total of 51 steps + one last page with less than 127 novels
URL = "https://tgstorytime.com/browse.php?type=titles&offset={}"  # listing all titles
NOVEL_LINK = "https://tgstorytime.com/{}"  # link to each title given the id
HOME_PAGE = "https://tgstorytime.com/index.php"  # log in first
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

Third Run: 07/02/2026 - TG Storytime has 6587 stories from 2007 authors (Last Checked: 00:39 of 08/02/2026)

Total Novel Count (Script Counter): 5013
Total Novel Count (Folder Counter): 5013
Total Nove Count (Manual Folder Counter): 1572
Failed Downloads: 2
Time taken: 652 minutes

Note 1: Using the COUNTER variable was a bit of a dumb idea, but it worked, I was able to find out the difference
between the folder and the script counter, it was as I suspected, there were works with the same title being
saved on top of another, in order to create unique names I should create a new naming convention, the name of the novel
plus the name of the author, the same author won't create more than one novel with the same name, so there won't be
any more duplications. 

Fourth Run: 09/02/2026 - TG Storytime has 6587 stories from 2007 authors

Total Novel Count (Script): 6583
Failed Downloads: 4
Time taken: 565 minutes
"""

ERRORS = []
DOWNLOAD_OK = []
COUNTER = 0


def count_novels():
    auto = Path(DOWNLOAD_DIR)
    manual = Path(TG_MANUAL_DOWNLOAD)
    novels = []
    for novel in auto.iterdir():
        novels.append(get_name(novel))
    for novel in manual.iterdir():
        novels.append(get_name(novel))
    novels.sort()
    for n in novels:
        if novels.count(n) > 1:
            print(n)
    s = set(novels)
    print(f"Novels Counter {len(novels)}")
    print(f"Set Counter: {len(s)}")
    print(f"Diff: {abs(len(novels) - len(s))}")


def get_name(novel):
    name = novel.name
    while name[0].isdigit():
        name = name[1:]
    return name


def find_empty_epubs(root_folder: str):
    """
    Just checking if there are any empty/blank files
    """
    root_path = Path(root_folder)

    print(f"\nScanning for empty .epub files under: {root_folder}\n")
    smallest = float("inf")
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
    print(f"Smallest File: {smallest_name} - {smallest / 1024:.2f} KB\n")


def get_novel_urls(page):  # sid = story id
    titles = []
    p = 1
    for offset in range(OFFSET, LIMIT + 1, STEP):
        page.goto(URL.format(offset), wait_until="domcontentloaded")
        anchors = page.locator("div.title a[href^='viewstory.php?sid=']")
        novels = []
        for i in range(anchors.count()):
            link = anchors.nth(i).get_attribute("href")
            novels.append(NOVEL_LINK.format(link))
        if p < 52:
            assert len(novels) == STEP, (
                f"\nExpected {STEP} novels, got {len(novels)} -> OFFSET: {offset}\n"
            )
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
    # page.fill("#password", password)
    page.get_by_role("textbox", name="password").fill(password)
    # <input type="submit" class="button" name="submit" value="Go">
    page.get_by_role("button", name="Go").click()
    # page.click('input[type="submit"][value="Go"]')
    print("\nLogged In Successfully\n")


def download_epub(page, novel_url, timeout=15_000):  # timeout -> 1000 = 1s
    """Returns path on success, None if download failed (e.g. server error)."""
    # global COUNTER
    try:
        # removed wait_until="domcontentloaded" because it's timing out constantly
        # now the script will wait till what's important appear
        page.goto(novel_url)
        base = page.locator('a[href*="epubversion/epubs/"][href$=".epub"]')
        epub_link = base.filter(has_text="Story").or_(
            base.filter(has_text="Download ePub")
        )
        epub_link.wait_for(state="visible", timeout=DOWNLOAD_LOCATOR_TIMEOUT)
        with page.expect_download(timeout=DOWNLOAD_EVENT_TIMEOUT) as download_info:
            # .click() also has timeout argument, but it's a fast event, so there is no need to set a higher timeout
            epub_link.click()
        author = page.locator('a[href*="viewuser.php?uid="]').inner_text()
        d = download_info.value
        # file_name = f"7912 {d.suggested_filename}"
        # COUNTER = COUNTER + 1
        title = d.suggested_filename.replace(".epub", "")
        file_name = f"{title} {author}.epub"
        path = os.path.join(DOWNLOAD_DIR, file_name)
        d.save_as(path)
        return True
    except Exception as e:
        try:
            print(
                f"$$$$AUTO$$$$$ AUTO FAILED (no download): {novel_url} - {e} $$$$$AUTO$$$$"
            )
            ERRORS.append(str(e))
            print(" \n\n ---> manual download\n")
            worked = manual_download(page, novel_url)
            return worked
        except Exception as ex:
            print(
                f"$$$MANUAL$$$$$$ MANUAL FAILED (no download): {novel_url} - {ex} $$$$MANUAL$$$$$"
            )
            ERRORS.append(str(ex))
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
    with open("failed_downloads_2.json", "w") as f:
        json.dump(failed, f)
    with open("success_2.json", "w") as sc:
        json.dump(DOWNLOAD_OK, sc)
    with open("ERRORS_3.json", "w") as file:
        json.dump(ERRORS, file)


def chapter_text_to_html(chapter_title: str, text: str) -> str:
    # Split on blank lines into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    body_html = "\n".join(f"<p>{p}</p>" for p in paragraphs)

    return f"""<html>
  <head>
    <title>{chapter_title}</title>
  </head>
  <body>
    <h2>{chapter_title}</h2>
    {body_html}
  </body>
</html>"""


def manual_download(page, title):
    """
    Manually download a novel by scraping chapters from a select dropdown.
    If a select element with class 'textbox' and name 'chapter' exists,
    downloads each chapter individually and saves them as separate files,
    plus saves all chapters combined as a single novel file.
    """
    # global COUNTER
    try:
        # Load the page
        page.goto(title, wait_until="domcontentloaded")

        # Check if the chapter select element exists
        chapter_select = page.locator('select.textbox[name="chapter"]')

        # Get all option values from the select
        options = chapter_select.locator("option")
        option_count = options.count()

        # Extract novel title from div.pagetitle: novel name (viewstory.php link) + author (viewuser.php link)
        pagetitle = page.locator("#pagetitle")
        novel_name = pagetitle.locator('a[href*="viewstory.php?sid="]').inner_text()
        author = pagetitle.locator('a[href*="viewuser.php?uid="]').inner_text()
        novel_title = f"{novel_name} - {author}"
        # Clean title for filename
        novel_title = "".join(
            c for c in novel_title if c.isalnum() or c in (" ", "-", "_")
        ).strip()

        # COUNTER = COUNTER + 1
        # novel_title = f"{COUNTER} {novel_title}"
        # Create directory for this novel's chapters
        novel_dir = os.path.join(TG_MANUAL_DOWNLOAD, novel_title)
        os.makedirs(novel_dir, exist_ok=True)

        # If no chapters found in select, download the current page's story content
        if option_count == 0:
            print(f"No chapters found in select for: {title}")
            print("Downloading single-page story content...")

            try:
                # Wait for the story content to load
                story_div = page.locator("#story")
                story_div.wait_for(state="visible", timeout=10000)
                page.wait_for_timeout(1000)

                # Extract text content from div#story
                story_content = story_div.inner_text()

                if story_content:
                    # Save as a single file
                    filename = f"{novel_title}.txt"
                    file_path = os.path.join(novel_dir, filename)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(f"{novel_title}\n")
                        f.write(f"{'=' * 80}\n\n")
                        f.write(story_content)

                    print(f"Saved story: {filename}")
                    return True
                else:
                    print(f"Warning: Empty content in div#story for: {title}")
                    return False
            except Exception as e:
                print(f"Error extracting story content: {e}")
                return False

        print(f"Found {option_count} chapters for: {title}")

        all_chapters_content = []
        epub_chapters = []

        # Iterate through each chapter option
        for i in range(option_count):
            option = options.nth(i)
            chapter_value = option.get_attribute("value")
            chapter_text = option.inner_text()

            while not chapter_text[0].isalpha(): # take the chapter number from the front (otherwise it will be numbered twice)
                chapter_text = chapter_text[1:]

            if not chapter_value:
                continue

            print(f"Downloading chapter {i + 1}/{option_count}: {chapter_text}")

            # Select the chapter option
            # Triggers whatever onchange / form behavior the site has wired to the chapters' dropdown.
            # * Submits the form and reloads the page with the new chapter,
            # OR
            # * Updates the #story content via JavaScript without a full reload.
            chapter_select.select_option(chapter_value)

            # Wait for the story content to load/update
            try:
                story_div = page.locator("#story")
                story_div.wait_for(state="visible", timeout=10000)
                # Small delay to ensure content is fully loaded
                page.wait_for_timeout(1000)
            except Exception as e:
                print(f"Warning: Could not wait for story div for chapter {i + 1}: {e}")
                continue

            # Extract text content from div#story
            try:
                story_content = page.locator("#story").inner_text()

                if story_content:
                    # Save individual chapter file
                    chapter_filename = f"{chapter_text}.txt"  # Chapter_{i + 1:04d}_
                    # Clean filename
                    chapter_filename = "".join(
                        c
                        for c in chapter_filename
                        if c.isalnum() or c in (" ", "-", "_", ".")
                    ).strip()
                    chapter_path = os.path.join(novel_dir, chapter_filename)

                    with open(chapter_path, "w", encoding="utf-8") as f:
                        f.write(f"{chapter_text}\n\n")
                        f.write(story_content)

                    # Add to combined content
                    all_chapters_content.append(f"\n\n{'=' * 80}\n")
                    all_chapters_content.append(f"Chapter {i + 1}: {chapter_text}\n")
                    all_chapters_content.append(f"{'=' * 80}\n\n")
                    all_chapters_content.append(story_content)
                    # epub
                    epub_chapters.append((chapter_text, story_content))

                    print(f"  Saved: {chapter_filename}")
                else:
                    print(f"  Warning: Empty content for chapter {i + 1}")
            except Exception as e:
                print(f"  Error extracting content for chapter {i + 1}: {e}")
                continue

        # Save combined novel file (txt) + EPUB
        if epub_chapters:
            # 1) Optional: keep your existing combined .txt file
            combined_filename = f"{novel_title}_Complete.txt"
            combined_path = os.path.join(novel_dir, combined_filename)
            with open(combined_path, "w", encoding="utf-8") as f:
                f.write(f"{novel_title}\n")
                f.write(f"{'=' * 80}\n\n")
                f.write("".join(all_chapters_content))
            print(f"\nSaved complete novel text: {combined_filename}")

            # 2) Build EPUB
            book = epub.EpubBook()
            book.set_identifier(novel_title)
            book.set_title(novel_title)
            book.add_author(author)

            # Basic stylesheet for “proper” ebook look
            style = """
            body {
                font-family: "Georgia", "Times New Roman", serif;
                line-height: 1.5;
                margin: 1em;
            }
            h1, h2 {
                text-align: center;
                margin: 1em 0;
            }
            p {
                text-indent: 1.2em;
                margin: 0 0 0.6em 0;
            }
            """

            nav_css = epub.EpubItem(
                uid="style_nav",
                file_name="style/nav.css",
                media_type="text/css",
                content=style,
            )
            book.add_item(nav_css)

            spine_items = ["nav"]
            toc_items = []

            for idx, (chapter_title, chapter_text) in enumerate(epub_chapters, start=1):
                html_content = chapter_text_to_html(chapter_title, chapter_text)
                chap = epub.EpubHtml(
                    title=chapter_title,
                    file_name=f"chap_{idx:04d}.xhtml",
                    lang="en",
                )
                chap.content = html_content
                # Attach stylesheet
                chap.add_item(nav_css)

                book.add_item(chap)
                spine_items.append(chap)
                toc_items.append(chap)

            book.toc = tuple(toc_items)
            book.spine = spine_items

            # Required navigation files
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            epub_filename = f"{novel_title}.epub"
            epub_path = os.path.join(novel_dir, epub_filename)
            epub.write_epub(epub_path, book, {})

            print(f"Saved EPUB: {epub_filename}")
            print(f"Total chapters downloaded: {len(epub_chapters)}\n")
            return True
        else:
            print(f"No content was downloaded for: {title}")
            return False

    except Exception as e:
        print(f"$$$$$$$$$ FAILED (manual download): {title} - {e} $$$$$$$$$")
        ERRORS.append(str(e))
        return False


def run():
    with sync_playwright() as p:
        # Launch browser (headless=True for invisible browser)
        # browser = p.chromium.launch(headless=False)
        browser = p.firefox.launch(headless=False)

        # Create a new context with a download directory
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        login(page)
        start = time.time()

        # titles = get_novel_urls(page)
        # download_all_epubs(page, titles)
        manual_download(page, "https://tgstorytime.com/viewstory.php?sid=9052")

        end = time.time()
        total_min = (end - start) / 60
        print(f"\n\n\nTime taken: {int(total_min)} minutes")

        browser.close()


if __name__ == "__main__":
    print("\n----------------- START ----------------------")
    # count_novels()
    run()

    # find_empty_epubs("V:\TG_STORY_TIME_2nd_Run")
