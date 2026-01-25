
OFFSET = 0 # start at frist page
STEP = 127 # each steap is a new web page
LIMIT = 6477 # a grand total of 51 steps
URL = "https://tgstorytime.com/browse.php?type=titles&offset={}"

# Example: How to update URL for new pages
def get_page_url(offset):
    """Generate URL for a specific page by offset"""
    return URL.format(offset)

# Iterate through all pages
def iterate_pages():
    """Iterate through all pages from OFFSET to LIMIT"""
    for offset in range(OFFSET, LIMIT + 1, STEP):
        page_url = get_page_url(offset)
        print(f"Page with offset {offset}: {page_url}")
        # Add your download logic here
        # process_page(page_url)

