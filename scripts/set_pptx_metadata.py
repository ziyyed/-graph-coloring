#!/usr/bin/env python3
"""Set the author and descriptive core properties in an OOXML PowerPoint file."""

from __future__ import annotations

import argparse
import os
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def set_metadata(path: Path, author: str, title: str, subject: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)

    with zipfile.ZipFile(path, "r") as source:
        entries = [(item, source.read(item.filename)) for item in source.infolist()]

    core_index = next((i for i, (item, _) in enumerate(entries)
                       if item.filename == "docProps/core.xml"), None)
    if core_index is None:
        raise ValueError("Le fichier PowerPoint ne contient pas docProps/core.xml.")

    info, xml_bytes = entries[core_index]
    root = ET.fromstring(xml_bytes)
    values = {
        f"{{{NS['dc']}}}creator": author,
        f"{{{NS['cp']}}}lastModifiedBy": author,
        f"{{{NS['dc']}}}title": title,
        f"{{{NS['dc']}}}subject": subject,
    }
    for tag, value in values.items():
        element = root.find(tag)
        if element is None:
            element = ET.SubElement(root, tag)
        element.text = value
    ET.register_namespace("cp", NS["cp"])
    ET.register_namespace("dc", NS["dc"])
    entries[core_index] = (info, ET.tostring(root, encoding="utf-8", xml_declaration=True))

    fd, temporary_name = tempfile.mkstemp(suffix=".pptx", dir=path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary_name, "w") as target:
            for item, content in entries:
                target.writestr(item, content)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--author", default="Zied Chouk, Chayma Hakouna, Wirak")
    parser.add_argument("--title", default="Le coloriage de graphes")
    parser.add_argument("--subject", default="Étude algorithmique et parallélisation OpenMP")
    args = parser.parse_args()
    set_metadata(args.pptx, args.author, args.title, args.subject)
    print(f"Métadonnées mises à jour : {args.pptx}")


if __name__ == "__main__":
    main()
