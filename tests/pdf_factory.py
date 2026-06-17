"""
Builds minimal valid PDFs for testing without external dependencies.
Uses pdfplumber's own dependency stack (pdfminer) indirectly — the PDFs produced
here are consumed by pdfplumber, so they only need to be structurally valid and
contain embedded text that pdfplumber can surface as table rows.
"""
import io


def _build_minimal_pdf(text_lines: list[str]) -> bytes:
    """Return bytes of a 1-page PDF whose content stream contains `text_lines`."""
    content_lines = []
    content_lines.append("BT")
    content_lines.append("/F1 10 Tf")
    y = 750
    for line in text_lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"50 {y} Td")
        content_lines.append(f"({safe}) Tj")
        content_lines.append("0 -14 Td")
        y -= 14
    content_lines.append("ET")
    content_stream = "\n".join(content_lines)
    content_bytes = content_stream.encode("latin-1", errors="replace")
    content_length = len(content_bytes)

    buf = io.BytesIO()

    def w(s: str):
        buf.write(s.encode("latin-1", errors="replace"))

    offsets: dict[int, int] = {}

    w("%PDF-1.4\n")

    offsets[1] = buf.tell()
    w("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    offsets[2] = buf.tell()
    w("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

    offsets[3] = buf.tell()
    w(
        "3 0 obj\n"
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        "   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
        "endobj\n"
    )

    offsets[4] = buf.tell()
    w(f"4 0 obj\n<< /Length {content_length} >>\nstream\n")
    buf.write(content_bytes)
    w("\nendstream\nendobj\n")

    offsets[5] = buf.tell()
    w(
        "5 0 obj\n"
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
        "endobj\n"
    )

    xref_offset = buf.tell()
    n = len(offsets) + 1
    w(f"xref\n0 {n}\n")
    w("0000000000 65535 f \n")
    for i in range(1, n):
        w(f"{offsets[i]:010d} 00000 n \n")

    w(f"trailer\n<< /Size {n} /Root 1 0 R >>\n")
    w(f"startxref\n{xref_offset}\n%%EOF\n")

    return buf.getvalue()


def valid_medicao_pdf() -> bytes:
    """A PDF whose text pdfplumber can extract as a table-like block."""
    lines = [
        "Servico  Descricao  Codigo SICRO  Unidade  Preco Unitario  Quantidade Acumulada",
        "56988  Pavimentacao asfaltica  1234567  m2  1.234,56  100,00",
        "54393  Terraplenagem geral  7654321  m3  890,00  200,00",
    ]
    return _build_minimal_pdf(lines)


def corrupt_pdf() -> bytes:
    return b"%PDF-1.4\nthis is not a real pdf"


def no_table_pdf() -> bytes:
    """Valid PDF whose content has no recognisable DNIT table header."""
    return _build_minimal_pdf(["Hello world", "No tables here at all."])
