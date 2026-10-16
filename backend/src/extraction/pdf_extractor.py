"""Robust pure-Python digital PDF text extraction helper.

Extracts text streams from digital PDFs (e.g. ReportLab or computer-generated police records)
without requiring third-party PDF binaries or external cloud API calls.
"""

from __future__ import annotations

import base64
import re
import zlib
from pathlib import Path


def extract_digital_pdf_pages(source_path: Path) -> list[str]:
    """Extract embedded text strings from unencrypted PDF streams with zlib/ASCII85 decoding.
    
    Returns a list of page strings (each string representing a page's text).
    Returns an empty list if the PDF has no embedded digital text (scanned image or corrupted file).
    """
    try:
        content = source_path.read_bytes()
    except OSError:
        return []

    # Stream blocks in PDF
    stream_matches = re.findall(rb"stream[\r\n]+(.*?)endstream", content, re.DOTALL)
    pages: list[str] = []
    for s in stream_matches:
        s_clean = s.strip()
        decomp = None
        # Try direct FlateDecode (zlib)
        try:
            decomp = zlib.decompress(s_clean)
        except Exception:
            pass
        # Try ASCII85Decode followed by FlateDecode
        if decomp is None:
            try:
                decomp = zlib.decompress(base64.a85decode(s_clean, adobe=True))
            except Exception:
                pass
        if decomp:
            texts = re.findall(rb"\((.*?)\)\s*Tj", decomp)
            if texts:
                clean_texts = [t.decode("latin1", errors="replace") for t in texts]
                page_str = "\n".join(clean_texts)
                if len(page_str.strip()) > 20:
                    pages.append(page_str)
    return pages
