import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import opencc

def convert_to_hk_traditional_chinese(epub_file_path):
    # Initialize OpenCC for Simplified to Hong Kong Traditional
    cc = opencc.OpenCC('s2hk')

    # Read the EPUB file
    book = epub.read_epub(epub_file_path)

    # Convert document contents
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # Parse HTML content
            content = item.get_content().decode('utf-8')
            soup = BeautifulSoup(content, 'html.parser')
            
            # Convert all text elements
            for text_node in soup.find_all(string=True):
                if text_node.parent.name not in ['style', 'script', 'head', 'meta', '[document]']:
                    original_text = str(text_node)
                    if original_text.strip():
                        converted_text = cc.convert(original_text)
                        text_node.replace_with(converted_text)
                        
            # Save the new content back to the item
            item.set_content(str(soup).encode('utf-8'))

    # Generate new file name
    directory = os.path.dirname(epub_file_path)
    filename = os.path.basename(epub_file_path)
    name, ext = os.path.splitext(filename)
    
    # Convert filename to Traditional as well
    new_name = cc.convert(name)
    new_filename = f"{new_name}_HK{ext}"
    output_path = os.path.join(directory, new_filename)

    # Save the output EPUB
    epub.write_epub(output_path, book)
    
    return new_filename
