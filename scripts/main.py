import os
import sys
from pathlib import Path
from downloader import download_book
from reformat import reformat
from epubber import create_epub

def main(base_url):
    download_book(base_url)

    script_dir = Path(__file__).parent.resolve()
    reformat(script_dir, os.path.join("Text", "index.html"))

    create_epub()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <base_url>")
        sys.exit(1)

    base_url = sys.argv[1]
    main(base_url)
