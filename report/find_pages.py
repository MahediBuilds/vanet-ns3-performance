"""Find the printed page number of every chapter, section, figure and table in a rendered PDF.
Usage: python find_pages.py REPORT.pdf KEYS.json OUT_pages.json
Printed page = PDF page index + 1 (numbering starts at 3 on the third page)."""
import json
import re
import sys

import pymupdf

pdf, keys, out = sys.argv[1:4]
K = json.load(open(keys))
doc = pymupdf.open(pdf)
texts = [re.sub(r"[ \t]+", " ", p.get_text()) for p in doc]
# body starts at the page that holds "CHAPTER 1"
start = next(i for i, t in enumerate(texts) if re.search(r"^CHAPTER 1\s*$", t, re.M))
pages = {}


def footer_number(page):
    nums = [b[4].strip() for b in page.get_text("blocks") if b[4].strip().isdigit() and b[1] > page.rect.height * 0.9]
    return int(nums[-1]) if nums else None


printed = [footer_number(p) for p in doc]


def find(pattern, key):
    for i in range(start, len(texts)):
        if re.search(pattern, texts[i], re.M):
            pages[key] = printed[i]
            return
    print("NOT FOUND", key, pattern)


for n in range(1, len(K["chapters"]) + 1):
    find(rf"^CHAPTER {n}\s*$", f"ch{n}")
for s in K["sections"]:
    num, title = s.split(" ", 1)
    find(rf"^{re.escape(num)} {re.escape(title.split()[0])}", num)
for left, cap in K["figs"] + K["tabs"]:
    words = cap.split()[:3]
    find(rf"^{re.escape(left)}\.\s+{re.escape(' '.join(words))}", left)
json.dump(pages, open(out, "w"), indent=1)
print(len(doc), "pages;", json.dumps(pages))
