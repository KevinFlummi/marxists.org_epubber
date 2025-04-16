import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def sanitize_filename(filename):
    """Sanitize filename to be filesystem-safe"""
    keep_chars = (' ', '.', '_', '-')
    return "".join(c if c.isalnum() or c in keep_chars else "" for c in filename)

def download_book(root_dir, base_url):
    try:
        # Download the main page
        print(f"Downloading main page: {base_url}")
        response = requests.get(base_url)
        response.raise_for_status()
        html = response.text
        # Handle malformed HTML from early 2000s
        html = re.sub(r'<(/?[A-Z]+)>', lambda m: m.group(0).lower(), html)  # Lowercase tags
        html = re.sub(r'<([^>]+)>', lambda m: m.group(0).replace('\\', '/'), html)  # Fix backslash

        # Parse the main page
        soup = BeautifulSoup(html, 'html.parser')

        # Get page title for folder name
        folder_name = os.path.join(root_dir, "Text")

        # Create output directory
        os.makedirs(folder_name, exist_ok=True)
        with os.scandir(folder_name) as entries:
            for entry in entries:
                if entry.is_file():
                    os.remove(entry.path)

        # Save main page as index.html
        with open(os.path.join(folder_name, "index.html"), 'w', encoding='utf-8') as f:
            f.write(html)
        print("Saved main page as index.html")

        # Find all links between the markers
        start_marker = soup.find('body')
        end_marker = soup.find('p', {'class': 'updat'})

        # Collect all unique links between these markers
        links = []
        current_element = start_marker.find_next() if start_marker else None
        while current_element and current_element != end_marker:
            if current_element.name == 'a' and current_element.get('href'):
                href = current_element['href']
                # Skip anchor links and non-HTML files
                if not href.startswith('#') and not href.startswith('mailto:') and not href.startswith('http') and not href.startswith('..') and not href.endswith(('.pdf', '.jpg', '.png', 'index.htm', 'index.html')) and not 'translator.htm' in href and not "#" in href.split(".")[-1]:
                    absolute_url = urljoin(base_url, href)
                    if absolute_url != base_url:  # Don't include the main page again
                        links.append(absolute_url)
            current_element = current_element.find_next()

        print(f"Found {len(links)} unique pages to download")

        # Download each unique page with sequential numbering
        for i, link in enumerate(links, 1):
            try:
                print(f"Downloading {i}/{len(links)}: {link}")
                time.sleep(1)  # Polite delay between requests
                response = requests.get(link)
                response.raise_for_status()

                # Save with sequential numbering
                filename = f"Section{i:03d}.xhtml"  # Formats as Section001.xhtml, Section002.xhtml, etc.
                filepath = os.path.join(folder_name, filename)

                html = response.text
                html = re.sub(r'<(/?[A-Z]+)>', lambda m: m.group(0).lower(), html)  # Lowercase tags
                html = re.sub(r'<([^>]+)>', lambda m: m.group(0).replace('\\', '/'), html)  # Fix backslash

                # Save the content
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html)

            except Exception as e:
                print(f"Failed to download {link}: {str(e)}")
                continue

        print(f"\nDownload complete! Files saved in: {folder_name}")
        print(f"- index.html (main page)")
        print(f"- {len(links)} section files (Section001.xhtml to Section{len(links):03d}.xhtml)")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_pages.py <base_url>")
        sys.exit(1)

    base_url = sys.argv[1]
    root_dir = os.path.join(__file__, "..")
    download_book(root_dir, base_url)
