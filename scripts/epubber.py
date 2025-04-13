import os
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import re

def get_metadata_from_opf(opf_path):
    """Extract title and author from content.opf"""
    try:
        tree = ET.parse(opf_path)
        root = tree.getroot()

        # Namespace handling
        ns = {'opf': 'http://www.idpf.org/2007/opf',
              'dc': 'http://purl.org/dc/elements/1.1/'}

        title = root.find('.//dc:title', ns).text
        author = root.find('.//dc:creator', ns).text

        # Clean filenames
        title = re.sub(r'[\\/*?:"<>|]', '_', title.strip())
        author = re.sub(r'[\\/*?:"<>|]', '_', author.strip())

        return title, author
    except Exception as e:
        raise ValueError(f"Could not parse metadata from {opf_path}: {str(e)}")

def create_epub(content_dir='.'):
    """Package an EPUB with automatic naming"""
    # Required EPUB paths
    paths = {
        'mimetype': os.path.join(content_dir, 'mimetype'),
        'container': os.path.join(content_dir, 'META-INF', 'container.xml'),
        'content_opf': os.path.join(content_dir, 'content.opf'),
        'text_dir': os.path.join(content_dir, 'Text'),
        'styles_dir': os.path.join(content_dir, 'Styles')
    }

    # Validate required files
    if not os.path.exists(paths['content_opf']):
        raise FileNotFoundError(f"Missing content.opf at {paths['content_opf']}")

    # Get metadata for filename
    title, author = get_metadata_from_opf(paths['content_opf'])

    # Create output directory structure
    output_dir = Path(os.path.join("library", author))
    output_dir.mkdir(exist_ok=True)
    epub_path = output_dir / f"{title}.epub"

    # Create EPUB (ZIP with specific structure)
    with zipfile.ZipFile(epub_path, 'w', zipfile.ZIP_DEFLATED) as epub:
        # 1. Add mimetype first (uncompressed)
        mimetype_path = paths['mimetype']
        if not os.path.exists(mimetype_path):
            with open(mimetype_path, 'w') as f:
                f.write('application/epub+zip')
        epub.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)

        # 2. Add container.xml
        container_dir = os.path.dirname(paths['container'])
        os.makedirs(container_dir, exist_ok=True)
        if not os.path.exists(paths['container']):
            with open(paths['container'], 'w') as f:
                f.write('''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>''')
        epub.write(paths['container'], 'META-INF/container.xml')

        # 3. Add content.opf
        epub.write(paths['content_opf'], 'content.opf')

        # 4. Add all HTML files in Text/
        if os.path.exists(paths['text_dir']):
            for root, _, files in os.walk(paths['text_dir']):
                for file in files:
                    if file.endswith(('.xhtml', '.html')):
                        full_path = os.path.join(root, file)
                        arc_path = os.path.relpath(full_path, content_dir)
                        epub.write(full_path, arc_path)

        # 5. Add all CSS files in Styles/
        if os.path.exists(paths['styles_dir']):
            for root, _, files in os.walk(paths['styles_dir']):
                for file in files:
                    if file.endswith('.css'):
                        full_path = os.path.join(root, file)
                        arc_path = os.path.relpath(full_path, content_dir)
                        epub.write(full_path, arc_path)

    print(f"Successfully created EPUB: {epub_path}")

if __name__ == '__main__':
    create_epub()
