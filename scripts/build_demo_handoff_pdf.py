#!/usr/bin/env python3
"""Build the Enclave demo handoff PDF from the Markdown source."""

from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "docs" / "demo-deployment-handoff.md"
DEFAULT_OUTPUT = ROOT / "output" / "pdf" / "enclave-demo-deployment-handoff.pdf"
DEFAULT_DOCS_COPY = ROOT / "docs" / "enclave-demo-deployment-handoff.pdf"

rl_config.invariant = True

PAGE_WIDTH, _PAGE_HEIGHT = letter
MARGIN_X = 0.72 * inch
MARGIN_TOP = 0.58 * inch
MARGIN_BOTTOM = 0.56 * inch
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X

ACCENT = colors.HexColor("#3B82F6")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#4B5563")
BORDER = colors.HexColor("#D1D5DB")


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ETitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=29,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ESub",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=MUTED,
            spaceAfter=13,
        )
    )
    styles.add(
        ParagraphStyle(
            name="EH2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15.5,
            leading=19,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="EBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.8,
            leading=14.1,
            textColor=INK,
            spaceAfter=5.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="EBullet",
            parent=styles["EBody"],
            leftIndent=15,
            firstLineIndent=-9,
            spaceAfter=3.2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ENum",
            parent=styles["EBody"],
            leftIndent=18,
            firstLineIndent=-14,
            spaceAfter=3.4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ECaption",
            parent=styles["EBody"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=10.5,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=3,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ECode",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=8.25,
            leading=10.3,
            textColor=INK,
            backColor=colors.HexColor("#F8FAFC"),
            borderColor=colors.HexColor("#E5E7EB"),
            borderWidth=0.5,
            borderPadding=6,
            spaceBefore=3,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="EMeta",
            parent=styles["EBody"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11.5,
            textColor=ACCENT,
            spaceAfter=0,
        )
    )
    return styles


def inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", escaped)


def resolve_image(source: Path, src: str) -> Path:
    for candidate in (ROOT / src, source.parent / src):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not resolve image path: {src}")


def image_flowable(source: Path, styles, alt: str, src: str):
    image_path = resolve_image(source, src)
    image = Image(str(image_path))
    scale = min(CONTENT_WIDTH / image.imageWidth, (3.45 * inch) / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale

    table = Table([[image]], colWidths=[image.drawWidth + 10])
    table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return KeepTogether(
        [
            Spacer(1, 4),
            table,
            Paragraph(inline_markdown(alt), styles["ECaption"]),
        ]
    )


def code_flowable(styles, text: str):
    wrapped_lines: list[str] = []
    for line in text.rstrip("\n").splitlines():
        while len(line) > 92:
            wrapped_lines.append(line[:92])
            line = "    " + line[92:]
        wrapped_lines.append(line)
    return Preformatted("\n".join(wrapped_lines), styles["ECode"])


def add_callout(story, styles):
    table = Table(
        [
            [
                Paragraph(
                    "Keep the admin Nostr key private. Never paste it into "
                    "Enclave chat or the admin assistant.",
                    styles["EMeta"],
                )
            ]
        ],
        colWidths=[CONTENT_WIDTH],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#BFDBFE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([table, Spacer(1, 9)])


def markdown_to_story(source: Path):
    styles = build_styles()
    story = []
    in_code = False
    code_lines: list[str] = []

    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()

        if line.startswith("```"):
            if in_code:
                story.append(code_flowable(styles, "\n".join(code_lines)))
                code_lines = []
                in_code = False
            else:
                in_code = True
                code_lines = []
            continue

        if in_code:
            code_lines.append(raw_line)
            continue

        if not line.strip():
            continue

        image_match = re.match(r"!\[(.*?)\]\((.*?)\)", line)
        if image_match:
            story.append(
                image_flowable(
                    source,
                    styles,
                    image_match.group(1),
                    image_match.group(2),
                )
            )
        elif line.startswith("# "):
            story.append(Paragraph(inline_markdown(line[2:]), styles["ETitle"]))
            story.append(
                Paragraph(
                    "Simple admin sign-in, onboarding, user testing, and "
                    "assistant setup for an already-created demo instance.",
                    styles["ESub"],
                )
            )
            add_callout(story, styles)
        elif line.startswith("## "):
            story.append(Paragraph(inline_markdown(line[3:]), styles["EH2"]))
        elif line.startswith("- "):
            story.append(
                Paragraph("- " + inline_markdown(line[2:]), styles["EBullet"])
            )
        elif numbered := re.match(r"^(\d+)\.\s+(.*)", line):
            story.append(
                Paragraph(
                    f"{numbered.group(1)}. {inline_markdown(numbered.group(2))}",
                    styles["ENum"],
                )
            )
        else:
            story.append(Paragraph(inline_markdown(line), styles["EBody"]))

    return story


def footer(canvas, _document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN_X, 0.48 * inch, PAGE_WIDTH - MARGIN_X, 0.48 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(MARGIN_X, 0.31 * inch, "Enclave Demo Deployment Handoff")
    canvas.drawRightString(
        PAGE_WIDTH - MARGIN_X,
        0.31 * inch,
        f"Page {canvas.getPageNumber()}",
    )
    canvas.restoreState()


def build_pdf(source: Path, output: Path, docs_copy: Path | None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    story = markdown_to_story(source)
    document = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=MARGIN_X,
        leftMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title="Enclave Demo Deployment Handoff",
        author="Enclave",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)

    if docs_copy:
        docs_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, docs_copy)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--docs-copy",
        type=lambda value: None if value == "" else Path(value),
        default=DEFAULT_DOCS_COPY,
        help="Second PDF copy for convenient docs-folder sharing. Use '' to skip.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_pdf(args.source, args.output, args.docs_copy)
    print(args.output)
    if args.docs_copy:
        print(args.docs_copy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
