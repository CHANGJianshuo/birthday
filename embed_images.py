#!/usr/bin/env python3
"""Embed images as base64 into the HTML card to make it self-contained."""
import base64
import re
import os
import mimetypes

HTML_FILE = "/home/birthday/card.html"
OUTPUT_FILE = "/home/birthday/index.html"
BASE_DIR = "/home/birthday"

with open(HTML_FILE, "r", encoding="utf-8") as f:
    html = f.read()

def to_data_uri(filepath):
    """Convert a file to a base64 data URI."""
    abs_path = os.path.join(BASE_DIR, filepath)
    if not os.path.exists(abs_path):
        print(f"  WARNING: {abs_path} not found, skipping")
        return filepath

    mime, _ = mimetypes.guess_type(abs_path)
    if not mime:
        if filepath.endswith('.jpg') or filepath.endswith('.jpeg'):
            mime = 'image/jpeg'
        elif filepath.endswith('.png'):
            mime = 'image/png'
        elif filepath.endswith('.gif'):
            mime = 'image/gif'
        else:
            mime = 'application/octet-stream'

    with open(abs_path, "rb") as f:
        data = base64.b64encode(f.read()).decode('ascii')

    size_kb = len(data) * 3 / 4 / 1024
    print(f"  Embedded: {filepath} ({size_kb:.0f}KB, {mime})")
    return f"data:{mime};base64,{data}"

# Replace all image src references (images/ and new_picture/)
def replace_img_src(match):
    prefix = match.group(1)
    path = match.group(2)
    suffix = match.group(3)
    data_uri = to_data_uri(path)
    return f'{prefix}{data_uri}{suffix}'

print("Embedding images...")
html = re.sub(
    r'(src=")((?:images|new_picture)/[^"]+)(")',
    replace_img_src,
    html
)

# Also replace in JS string literals: 'images/...' and 'new_picture/...'
def replace_js_src(match):
    path = match.group(1)
    data_uri = to_data_uri(path)
    return f"'{data_uri}'"

html = re.sub(
    r"'((?:images|new_picture)/[^']+)'",
    replace_js_src,
    html
)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

output_size = os.path.getsize(OUTPUT_FILE)
print(f"\nDone! Output: {OUTPUT_FILE}")
print(f"File size: {output_size / 1024:.0f}KB ({output_size / 1024 / 1024:.1f}MB)")
