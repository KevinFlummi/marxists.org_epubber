import os
import re
import sys
from fuzzywuzzy import fuzz
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def german_fuzzy_match(text1, text2, threshold=85):
    """Special handling for German grammatical variations"""
    # Normalize common German variations
    replacements = {
        r'\bder\b': '(der|des|dem|den)',  # Articles
        r'\bdas\b': '(das|dem|des)',
        r'\bdie\b': '(die|der|den)',
        r'\bein\b': '(ein|einen|eines|einem|einer)',
        r'(\w+)s\b': r'\1(s|es)?'  # Genitive/plural forms
    }

    # Create flexible patterns
    pattern1 = text1.lower()
    pattern2 = text2.lower()

    for rgx, replacement in replacements.items():
        pattern1 = re.sub(rgx, replacement, pattern1)
        pattern2 = re.sub(rgx, replacement, pattern2)

    # Check direct match with normalized patterns
    if re.fullmatch(pattern1, text2.lower()) or re.fullmatch(pattern2, text1.lower()):
        return True

    # Fallback to fuzzy matching
    return fuzz.token_set_ratio(text1, text2) >= threshold

def generate_epub_toc(toc_data, template_path, output_path, title):
    """
    Generates an EPUB navigation file with unnumbered/unbulleted TOC

    Args:
        toc_data: Dictionary like {'':[sec1,sec2], 'chapter1':[sec3,sec4]}
        template_path: Path to nav.xhtml template
        output_path: Where to save the result
        title: Book title to replace $(title)
    """
    # Generate the TOC list
    nav_items = []

    section_num = 0
    # Add unindented items (prefaces, etc.)
    if '' in toc_data:
        for section in toc_data['']:
            section_num += 1
            nav_items.append(f'<li class="toc-item"><a href="Section{section_num:03d}.xhtml">{section}</a></li>')

    # Add chapters with subsections
    for chapter, sections in toc_data.items():
        if chapter == '':  # Skip the preface key
            continue

        nav_items.append(f'<li class="toc-chapter"><a href="Subtitle{section_num+1:03d}.xhtml">{chapter}</a>')
        if sections:
            nav_items.append('<ul class="toc-sublist">')
            for section in sections:
                section_num += 1
                nav_items.append(f'<li class="toc-item"><a href="Section{section_num:03d}.xhtml">{section}</a></li>')
            nav_items.append('</ul>')
        nav_items.append('</li>')

    # Join all items with newlines and proper indentation
    navlist = "\n    ".join(nav_items)

    # Read and process template
    template = Path(template_path).read_text(encoding='utf-8')
    processed = template.replace('$(title)', title).replace('$(navlist)', navlist)

    # Write output
    Path(output_path).write_text(processed, encoding='utf-8')



def generate_titlepage(template_path, output_path, title, author, date, subtitle=None):
    template = Path(template_path).read_text(encoding='utf-8')
    if subtitle:
        processed = template.replace('$(title)', title).replace('$(author)', author).replace('$(author)', author).replace('$(date)', date).replace('$(subtitle)', subtitle)
    else:
        processed = template.replace('$(title)', title).replace('$(author)', author).replace('$(author)', author).replace('$(date)', date).replace('<h2>$(subtitle)</h2>', '')
    Path(output_path).write_text(processed, encoding='utf-8')

def clean_legacy_html(html_content):
    """Properly handles anchor tags without duplication"""
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. First convert all entities to proper characters
    entity_map = {
        '&#8222;': '„',
        '&#8220;': '“',
        '&#8211;': '–',
        '&#223;': 'ß',
        '&#252;': 'ü',
        '&#220;': 'Ü',
        '&#228;': 'ä',
        '&#196;': 'Ä',
        '&#246;': 'ö',
        '&#214;': 'Ö',
        '&#8230;': '…'
    }

    # 2. Clean attributes while preserving structure
    for tag in soup.find_all(True):
        # Remove all attributes except these
        if hasattr(tag, 'attrs'):
            attrs_to_keep = {'href', 'id', 'name'}
            tag.attrs = {k: v for k, v in tag.attrs.items()
                        if k in attrs_to_keep}

    # 2.5. Remove <p class="footer"> and <p class="next"> elements entirely
    for class_name in ['footer', 'next', 'updat', ]:
        for tag in soup.find_all('p', class_=class_name):
            tag.decompose()

    # Remove specific "Anfang der Seite" paragraph
    output = str(soup)
    output = re.sub(
        r'<p[^>]*>\s*<a\s[^>]*href="#top"[^>]*>Anfang der Seite</a>\s*</p>',
        '',
        output,
        flags=re.IGNORECASE
    )
    soup = BeautifulSoup(output, 'html.parser')

    # 2.6. Remove everything after the last <p> tag
    all_p = soup.find_all('p')
    if all_p:
        last_p = all_p[-1]
        next_node = last_p.next_sibling
        while next_node:
            to_remove = next_node
            next_node = next_node.next_sibling
            if hasattr(to_remove, 'decompose'):
                to_remove.decompose()
            else:
                to_remove.extract()

    # 3. Special handling for paragraphs
    for p in soup.find_all('p'):
        # Only process paragraphs that actually contain text
        if p.get_text(strip=True):
            # Clean up spacing around elements
            for content in p.contents:
                if isinstance(content, str):
                    # Normalize whitespace
                    new_content = ' '.join(content.split())
                    content.replace_with(new_content)

    # 4. Convert to string and final cleanup
    output = str(soup)

    # Replace entities
    for entity, replacement in entity_map.items():
        output = output.replace(entity, replacement)

    # Add space before opening tags if missing
    output = re.sub(r'(?<!\s)(<[^/!][^>]*>)', r' \1', output)
    # Add space after closing tags if missing
    output = re.sub(r'(</[^>]+>)(?!\s)', r'\1 ', output)
    # Clean up any double spaces created
    output = re.sub(r'  +', ' ', output)

    # Fix common spacing issues
    output = re.sub(r'\s+([.,;:!?“”])', r'\1', output)  # Remove space before punctuation
    output = re.sub(r'([„(])\s+', r'\1', output)        # Remove space after opening quotes/parens

    # Ensure anchors stay within paragraphs
    output = re.sub(r'(</a>)\s*(</p>)', r'\1\2', output)
    output = re.sub(r'(<p[^>]*>)\s*(<a)', r'\1\2', output)
    output = output.replace('<br>', '<br/>')
    output = output.replace('<hr>', '<hr/>')
    output = re.sub(r'<a[^>]*>\s*(?:&nbsp;|\s)*</a>', '', output)
    output = re.sub(r'<p[^>]*>\s*(?:&nbsp;|\s)*</p>', '', output)

    return output


def reformat(script_dir, input_file):
    print("Reformatting book...")
    try:
        # Read the local file
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        folder_path = os.path.dirname(input_file)

        # Parse with BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')

        # Find author and title (always first h2 and h1 of page)
        page_title = soup.title.string.strip() if soup.title else "Datum unbekannt"
        if page_title != "Datum unbekannt":
            date_string = page_title.split("(")[-1]
            date = date_string.split(")")[0]
        else:
            date = page_title
        author = soup.find('h2').text
        title_elem = soup.find('h1')
        title = title_elem.text
        title = title.replace("\n", "")
        subtitle = None
        potential_subtitle = title_elem.next_sibling
        print(potential_subtitle)
        if potential_subtitle.name in ['h1', 'h2', 'h3', 'h4']:
            subtitle = potential_subtitle.text
            if subtitle == f"({date})":
                subtitle = None
        output_path = Path(os.path.join(folder_path, "titlepage.xhtml"))
        template_path = Path(os.path.join(script_dir, "..", "templates", "titlepage.xhtml"))
        template = template_path.read_text(encoding='utf-8')
        generate_titlepage(template_path, output_path, title, author, date, subtitle)

        # Find all links between the markers
        start_marker = soup.find('p')
        end_marker = soup.find('p', {'class': 'updat'})
        # Collect all unique links between these markers
        nav_dict = {}
        counter = 0
        current_subtitle = ""
        nav_dict[current_subtitle] = []
        current_element = start_marker.find_next() if start_marker else None
        while current_element and current_element != end_marker:
            if current_element.name == 'a' and current_element.get('href'):
                href = current_element['href']
                # Skip anchor links and non-HTML files
                if not href.startswith('#') and not href.startswith('mailto:') and not href.startswith('http') and not href.startswith('..') and not href.endswith(('.pdf', '.jpg', '.png', 'index.htm', 'index.html')) and not 'translator.htm' in href and not "#" in href.split(".")[-1]:
                    nav_dict[current_subtitle].append(current_element.text)
                    counter += 1
            elif current_element.name in ['h1', 'h2', 'h3', 'h4'] and not current_element.text.lower().startswith("content"):
                num = counter+1
                subtitle_filename = f"Subtitle{num:03d}.xhtml"
                subtitle_path = Path(os.path.join(folder_path, subtitle_filename))
                template_path = Path(os.path.join(script_dir, "..", "templates", "SubtitleXXX.xhtml"))
                template = template_path.read_text(encoding='utf-8')
                updated_content = template.replace("$(title)", current_element.text)
                subtitle_path.write_text(updated_content, encoding='utf-8')
                current_subtitle = current_element.text
                nav_dict[current_subtitle] = []

            current_element = current_element.find_next()
        template_path = Path(os.path.join(script_dir, "..", "templates", "nav.xhtml"))
        nav_path = Path(os.path.join(folder_path, "nav.xhtml"))
        generate_epub_toc(nav_dict, template_path, nav_path, title)

        # Next, edit the section files to be readable...
        sections = []
        for secs in nav_dict.values():
            sections.extend(secs)
        for i, section in enumerate(sections, 1):
            section_file = Path(os.path.join(folder_path, f"Section{i:03d}.xhtml"))
            content = section_file.read_text(encoding='utf-8')
            soup = BeautifulSoup(content, 'html.parser')
            current_element = soup.find('body')
            found_title = False
            search_words = set(section.lower().split())
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                heading_text = heading.get_text(' ', strip=True).lower()
                if german_fuzzy_match(section, heading_text):
                    found_title = True
                    break
                heading_words = set(heading_text.split())
                common_words = search_words & heading_words
                if len(common_words) >= max(1, 0.8*len(search_words)) or len(common_words) >= max(1, 0.8*len(heading_words)): # at least 80% words matching
                    found_title = True
                    break
            if not heading:
                break
            current_element = heading
            h1 = soup.new_tag('h1')
            h1.extend(current_element.contents)
            current_element.replace_with(h1)
            current_element = h1
            extracted = []
            end = soup.find('p', {'class':'updat'})
            while current_element and current_element != end:
                extracted.append(str(current_element))
                current_element = current_element.next_sibling
            dirty = '\n'.join(extracted)
            clean = clean_legacy_html(dirty)
            template_path = Path(os.path.join(script_dir, "..", "templates", "SectionXXX.xhtml"))
            template = template_path.read_text(encoding='utf-8')
            template = template.replace("$(body)", clean)
            template = template.replace("$(sectiontitle)", section)
            section_file.write_text(template, encoding='utf-8')

        # next, just fill out the content.opf and move everything into the required structure (if required i guess)
        template_path = Path(os.path.join(script_dir, "..", "templates", "content.opf"))
        template = template_path.read_text(encoding="utf-8")
        template = template.replace("$(title)", title)
        template = template.replace("$(author)", author)

        manifest = []
        spine = []
        for i in range(1, len(sections)+1):
            if f"Subtitle{i:03d}.xhtml" in os.listdir("Text"):
                mani = f'    <item id="Subtitle{i:03d}.xhtml" href="Text/Subtitle{i:03d}.xhtml" media-type="application/xhtml+xml"/>'
                spi = f'    <itemref idref="Subtitle{i:03d}.xhtml"/>'
                manifest.append(mani)
                spine.append(spi)

            mani = f'    <item id="Section{i:03d}.xhtml" href="Text/Section{i:03d}.xhtml" media-type="application/xhtml+xml"/>'
            spi = f'    <itemref idref="Section{i:03d}.xhtml"/>'
            manifest.append(mani)
            spine.append(spi)
        manifest_text = "\n".join(m for m in manifest)
        spine_text = "\n".join(s for s in spine)
        template = template.replace("$(manifest)", manifest_text)
        template = template.replace("$(spine)", spine_text)
        out = Path(os.path.join(script_dir, "..", "content.opf"))
        out.write_text(template, encoding='utf-8')

        os.remove(input_file)
        print("Finished reformatting")

    except Exception as e:
        print(f"Error processing file: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_local.py <input_file.html>")
        sys.exit(1)

    script_dir = Path(__file__).parent.resolve()
    input_file = sys.argv[1]
    reformat(script_dir, input_file)
