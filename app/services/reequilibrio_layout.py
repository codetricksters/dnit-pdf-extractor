"""Where everything sits on the Reequilíbrio sheet.

One module so the three places that need to agree cannot drift: the script that
builds the initial template, the export that writes into it, and the validation
that accepts a template the user uploaded.
"""

# Sheet the export writes to. A template whose sheet has another name is refused
# on upload rather than silently producing an empty spreadsheet.
ABA = "REEQUILÍBRIO"

TITULO = "ESTUDO REEQUILÍBRIO DOS MATERIAIS BETUMINOSOS"

# Contract block: label in B, value in C.
LINHA_CABECALHO_INICIO = 3
LINHA_CABECALHO_FIM = 13

# label → the contract field feeding it. ``None`` = filled by a template
# formula, not by the export.
CAMPOS_CABECALHO: list[tuple[str, str | None]] = [
    ("Contrato: ", "numero"),
    ("Edital:", "edital"),
    ("Rodovia:", "rodovia"),
    ("Trecho: ", "trecho"),
    ("Subtrecho:", "subtrecho"),
    ("Segmento:", "segmento"),
    ("Extensão: ", "extensao"),
    ("Contratada: ", "contratada"),
    ("Processo:", "numero_processo"),
    ("Data base:", "data_base"),
    ("Período:", None),  # template formula over the measurement months
]

# Legend for the memória de cálculo, beside the equation text box.
LINHA_LEGENDA_INICIO = 10
LEGENDA = [
    "∆𝑃= Variação do Preço Produtor calculado nos termos do artigo 16",
    "PI = Valor medido a preços iniciais",
    "R = Valor Medido referente a parcela de reajustamento",
    "m = Mês de Análise do REF",
]

# Table header spans rows 14–16: names, a blank band, and the letters that tie
# each column to the equation.
LINHA_HEADER = 14
LINHA_LETRAS = 16
PRIMEIRA_LINHA = 17  # first row the export writes

COL_INICIO = 2  # B
COL_FIM = 11  # K

COL_MES = 2
COL_DESCRICAO = 3
COL_VALOR_PI = 4
COL_FATOR = 5
COL_REAJUSTAMENTO = 6
COL_DELTA_P = 7
COL_TOTAL_PRODUTOR = 8
COL_REF_BRUTO = 9
COL_REF_SEM_LUCRO = 10

CABECALHOS = {
    COL_MES: "MEDIÇÃO (MÊS)",
    COL_DESCRICAO: "DESCRIÇÃO",
    COL_VALOR_PI: "VALOR\n A PI",
    COL_FATOR: "FATOR DE REAJUSTE",
    COL_REAJUSTAMENTO: "REAJUSTAMENTO DA MEDIÇÃO (R)",
    COL_TOTAL_PRODUTOR: "REAJUSTAMENTO TOTAL USANDO BASE PRODUTOR",
    COL_REF_BRUTO: "REF BRUTO COM LUCRO",
    COL_REF_SEM_LUCRO: "REF SEM LUCRO",
}

# Row 16: how each column enters the equation.
LETRAS = {
    COL_VALOR_PI: "a",
    COL_REAJUSTAMENTO: "b",
    COL_DELTA_P: "d",
    COL_TOTAL_PRODUTOR: "c = a*d",
    COL_REF_BRUTO: "e = c - b",
    COL_REF_SEM_LUCRO: "f = e * (1-(5,11/100))",
}

# Model rows in the template: the export copies their formatting for every row
# it writes, then removes them. Keeping formatting in the template — instead of
# building styles in code — is what lets the user restyle the spreadsheet in
# Excel without touching the application.
LINHA_GRUPO = 17
LINHA_DADOS = 18
LINHA_SUBTOTAL = 19
LINHA_TOTAL = 20
LINHAS_MODELO = (LINHA_GRUPO, LINHA_DADOS, LINHA_SUBTOTAL, LINHA_TOTAL)

ROTULO_SUBTOTAL = "SUBTOTAL"
ROTULO_TOTAL = "TOTAL REEQUILÍBRIO"

# Deducted from the gross REF, per the reference spreadsheet's column f.
LUCRO = "0.0511"
