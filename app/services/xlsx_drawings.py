"""Carrying text boxes across an openpyxl round-trip.

**openpyxl deletes text boxes.** Loading a workbook and saving it keeps the
images but drops every shape: verified on the reference workbook, whose
``drawing2.xml`` goes from 14 text runs (the ``REF = Σ …`` equation) to none.

That equation is the *memória de cálculo* the export must carry, and it has to
stay a native, vector, editable object — not a rendered image — so it prints and
zooms without loss and the user can change it in Excel.

So the export reads the shape anchors out of the template and re-inserts them
into the file openpyxl just wrote. Reading them from the template at export time,
rather than hard-coding them here, is what keeps the user's own equation as the
source of truth: edit the template and the export follows.

The work is done on the raw OPC package with string surgery. The alternative —
teaching openpyxl to model shapes — is far more code for a feature used once.
"""

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

NS_PACOTE = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PLANILHA = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
TIPO_DESENHO = f"{NS_DOC}/drawing"
TIPO_DESENHO_CT = (
    "application/vnd.openxmlformats-officedocument.drawing+xml"
)

# Anchor elements that can hold a shape. They never nest, so a non-greedy match
# per tag is unambiguous.
_ANCORAS = ("oneCellAnchor", "twoCellAnchor", "absoluteAnchor")

_WSDR_VAZIO = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/'
    'spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/'
    '2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships">{conteudo}</xdr:wsDr>'
)


class TemplateInvalido(Exception):
    """The template is not a workbook this code can work with."""


def _ler(caminho: Path | bytes) -> dict[str, bytes]:
    """Read an xlsx into a name → bytes mapping."""
    try:
        if isinstance(caminho, bytes):
            zf = zipfile.ZipFile(io.BytesIO(caminho))
        else:
            zf = zipfile.ZipFile(caminho)
        with zf:
            return {n: zf.read(n) for n in zf.namelist()}
    except zipfile.BadZipFile as e:
        raise TemplateInvalido("O arquivo não é um .xlsx válido.") from e


def _escrever(partes: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, dados in partes.items():
            zf.writestr(nome, dados)
    return buffer.getvalue()


def _relacionamentos(partes: dict[str, bytes], rels_path: str) -> list[dict[str, str]]:
    """Parse a .rels part.

    Parsed as XML rather than matched with a regex because attribute order is
    not fixed: Excel writes ``Id`` first, openpyxl writes it last, and the
    export has to read both.
    """
    if rels_path not in partes:
        return []
    raiz = ElementTree.fromstring(partes[rels_path])
    return [no.attrib for no in raiz]


def caminho_da_aba(partes: dict[str, bytes], nome_aba: str) -> str:
    """Path of the worksheet part holding *nome_aba*."""
    raiz = ElementTree.fromstring(partes["xl/workbook.xml"])
    rid = None
    for no in raiz.iter(f"{{{NS_PLANILHA}}}sheet"):
        if no.get("name") == nome_aba:
            rid = no.get(f"{{{NS_DOC}}}id")
            break
    if rid is None:
        raise TemplateInvalido(f"A planilha não contém a aba '{nome_aba}'.")

    for rel in _relacionamentos(partes, "xl/_rels/workbook.xml.rels"):
        if rel.get("Id") == rid:
            destino = rel["Target"].lstrip("/")
            return destino if destino.startswith("xl/") else f"xl/{destino}"
    raise TemplateInvalido(f"Relacionamento {rid} ausente na planilha.")


def _caminho_do_desenho(partes: dict[str, bytes], caminho_aba: str) -> str | None:
    pasta, arquivo = caminho_aba.rsplit("/", 1)
    for rel in _relacionamentos(partes, f"{pasta}/_rels/{arquivo}.rels"):
        if rel.get("Type") != TIPO_DESENHO:
            continue
        alvo = rel["Target"]
        if alvo.startswith("/"):
            return alvo.lstrip("/")
        return f"xl/{alvo[3:]}" if alvo.startswith("../") else f"{pasta}/{alvo}"
    return None


@dataclass
class Formas:
    """Shape anchors lifted from a drawing, with the namespaces they need.

    The declarations travel with the blocks because they live on the source
    drawing's root element, not inside the anchors. Injecting the blocks
    without them yields an "unbound prefix" parse error — Excel's shapes use
    prefixes (``a14``, ``mc``, …) that openpyxl's drawing root never declares.
    """

    blocos: list[str] = field(default_factory=list)
    declaracoes: dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.blocos)

    def __len__(self) -> int:
        return len(self.blocos)


def extrair_formas(origem: Path | bytes, nome_aba: str) -> Formas:
    """Anchor blocks containing a shape (text box).

    Images are left out on purpose: openpyxl preserves those by itself, and
    re-inserting them would duplicate the logo.
    """
    partes = _ler(origem)
    caminho_aba = caminho_da_aba(partes, nome_aba)
    caminho_desenho = _caminho_do_desenho(partes, caminho_aba)
    if not caminho_desenho or caminho_desenho not in partes:
        return Formas()

    xml = partes[caminho_desenho].decode("utf-8")
    blocos = []
    for ancora in _ANCORAS:
        padrao = re.compile(
            r"<(\w+:)?%s\b.*?</(\w+:)?%s>" % (ancora, ancora), re.DOTALL
        )
        for bloco in padrao.finditer(xml):
            texto = bloco.group(0)
            if re.search(r"<(\w+:)?sp\b", texto):
                blocos.append(texto)
    return Formas(blocos=blocos, declaracoes=_declaracoes_da_raiz(xml))


def _declaracoes_da_raiz(xml: str) -> dict[str, str]:
    """``prefixo → URI`` declared on the drawing's root element."""
    raiz = re.search(r"<(\w+:)?wsDr\b[^>]*>", xml)
    if not raiz:
        return {}
    return dict(re.findall(r'xmlns:(\w+)="([^"]+)"', raiz.group(0)))


def contem_equacao(origem: Path | bytes, nome_aba: str) -> bool:
    """Whether the sheet carries a text box with any text in it.

    Used to reject a template whose memória de cálculo went missing — which
    would otherwise produce a spreadsheet that looks right but omits the
    formula the calculation is justified by.
    """
    for bloco in extrair_formas(origem, nome_aba).blocos:
        if re.search(r"<a:t>[^<]", bloco):
            return True
    return False


def injetar_formas(conteudo: bytes, nome_aba: str, formas: Formas) -> bytes:
    """Return *conteudo* with *formas* added to the drawing of *nome_aba*.

    Creates the drawing part, its relationship and its content-type override
    when the sheet has none — which happens whenever the template carries no
    image for openpyxl to preserve.
    """
    if not formas:
        return conteudo

    partes = _ler(conteudo)
    caminho_aba = caminho_da_aba(partes, nome_aba)
    caminho_desenho = _caminho_do_desenho(partes, caminho_aba)
    conteudo = "".join(formas.blocos)

    if caminho_desenho and caminho_desenho in partes:
        xml = partes[caminho_desenho].decode("utf-8")
        fechamento = re.search(r"</(\w+:)?wsDr>", xml)
        if not fechamento:
            raise TemplateInvalido(
                f"Desenho inesperado em {caminho_desenho}; não foi possível "
                "reinserir a memória de cálculo."
            )
        xml = _declarar_namespaces(xml, formas.declaracoes)
        fechamento = re.search(r"</(\w+:)?wsDr>", xml)
        inicio = fechamento.start()
        partes[caminho_desenho] = (xml[:inicio] + conteudo + xml[inicio:]).encode("utf-8")
    else:
        caminho_desenho = _novo_caminho_de_desenho(partes)
        xml = _declarar_namespaces(
            _WSDR_VAZIO.format(conteudo=conteudo), formas.declaracoes
        )
        partes[caminho_desenho] = xml.encode("utf-8")
        _vincular_desenho(partes, caminho_aba, caminho_desenho)
        _registrar_tipo_de_conteudo(partes, caminho_desenho)

    return _escrever(partes)


def injetar_formas_em_arquivo(caminho: Path, nome_aba: str, formas: Formas) -> None:
    """In-place variant, for the one-off template build script."""
    caminho.write_bytes(injetar_formas(caminho.read_bytes(), nome_aba, formas))


def _declarar_namespaces(xml: str, declaracoes: dict[str, str]) -> str:
    """Add the missing ``xmlns:`` declarations to the drawing's root element."""
    raiz = re.search(r"<(\w+:)?wsDr\b[^>]*>", xml)
    if not raiz:
        return xml
    abertura = raiz.group(0)
    presentes = _declaracoes_da_raiz(xml)
    faltando = "".join(
        f' xmlns:{prefixo}="{uri}"'
        for prefixo, uri in declaracoes.items()
        if prefixo not in presentes
    )
    if not faltando:
        return xml
    nova = abertura.rstrip(">").rstrip("/") + faltando + ">"
    return xml[: raiz.start()] + nova + xml[raiz.end():]


def _novo_caminho_de_desenho(partes: dict[str, bytes]) -> str:
    usados = {
        int(m.group(1))
        for nome in partes
        if (m := re.fullmatch(r"xl/drawings/drawing(\d+)\.xml", nome))
    }
    n = 1
    while n in usados:
        n += 1
    return f"xl/drawings/drawing{n}.xml"


def _vincular_desenho(
    partes: dict[str, bytes], caminho_aba: str, caminho_desenho: str
) -> None:
    pasta, arquivo = caminho_aba.rsplit("/", 1)
    rels_path = f"{pasta}/_rels/{arquivo}.rels"
    alvo = "../" + caminho_desenho[len("xl/"):]

    if rels_path in partes:
        rels = partes[rels_path].decode("utf-8")
        usados = {int(m) for m in re.findall(r'Id="rId(\d+)"', rels)}
        rid = f"rId{max(usados, default=0) + 1}"
        rels = rels.replace(
            "</Relationships>",
            f'<Relationship Id="{rid}" Type="{TIPO_DESENHO}" Target="{alvo}"/>'
            "</Relationships>",
        )
    else:
        rid = "rId1"
        rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{NS_PACOTE}">'
            f'<Relationship Id="{rid}" Type="{TIPO_DESENHO}" Target="{alvo}"/>'
            "</Relationships>"
        )
    partes[rels_path] = rels.encode("utf-8")

    aba = partes[caminho_aba].decode("utf-8")
    if re.search(r"<drawing\b", aba):
        return
    # <drawing> sits near the end of CT_Worksheet's sequence.
    aba = aba.replace("</worksheet>", f'<drawing r:id="{rid}"/></worksheet>')
    partes[caminho_aba] = aba.encode("utf-8")


def _registrar_tipo_de_conteudo(partes: dict[str, bytes], caminho: str) -> None:
    ct = partes["[Content_Types].xml"].decode("utf-8")
    if f'PartName="/{caminho}"' in ct:
        return
    ct = ct.replace(
        "</Types>",
        f'<Override PartName="/{caminho}" ContentType="{TIPO_DESENHO_CT}"/></Types>',
    )
    partes["[Content_Types].xml"] = ct.encode("utf-8")
