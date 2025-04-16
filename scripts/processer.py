import os
import sys
from pathlib import Path
from downloader import download_book
from reformat import reformat
from epubber import create_epub

def from_url(base_url):
    script_dir = Path(__file__).parent.resolve()
    root_dir = script_dir.parent.resolve()

    download_book(root_dir, base_url)

    reformat(script_dir, os.path.join(root_dir, "Text", "index.html"))

    fpath = create_epub(root_dir)
    return fpath


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <base_url>")
        sys.exit(1)

    base_url = sys.argv[1]
    from_url(base_url)
