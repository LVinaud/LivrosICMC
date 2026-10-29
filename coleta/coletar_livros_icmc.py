"""
Coleta os livros da Biblioteca do ICMC pela Busca Integrada da USP (Primo).

Fluxo:
  1. Para cada ano de publicação, faz a busca filtrada (Biblioteca = ICMC, Tipo = Livros, Ano = ano)
     e anota os IDs dos registros. A busca é feita ano a ano porque o site só deixa paginar
     até ~490 resultados por busca.
  2. Para cada ID, baixa o registro completo em XML (PNX) e extrai os campos.
  3. Salva tudo em dados/livros_icmc.csv.

Coleta educada: uma requisição por vez, com pausa entre elas, e cache local dos XMLs
(rodar de novo não baixa o que já foi baixado). O Dedalus não é acessado (o robots.txt dele proíbe robôs).

Uso:
  python coletar_livros_icmc.py                 # todos os anos
  python coletar_livros_icmc.py 2015 2016       # só livros publicados de 2015 a 2016
"""
import csv
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

BASE = "https://www.buscaintegrada.usp.br/primo_library/libweb/action/"
PAUSA = 2  # segundos entre requisições
LIMITE = 490  # o site não deixa paginar além de ~490 resultados por busca
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados")
NS = {"p": "http://www.exlibrisgroup.com/xsd/primo/primo_nm_bib"}

sessao = requests.Session()
sessao.headers["User-Agent"] = "Projeto academico SCC0252 Visualizacao Computacional ICMC-USP"


def buscar_pagina(periodo, pagina):
    """Uma página (10 livros) da busca pelos livros do ICMC publicados no período, ex.: "[2015 TO 2015]".
    Retorna (total de resultados da busca, IDs dos livros da página). pagina = 0, 1, 2, ..."""
    if pagina == 0:
        navegacao = [("ct", "search")]
    else:  # o site avança uma página a partir do índice da página anterior
        navegacao = [("ct", "Next Page"), ("pag", "nxt"), ("indx", 10 * pagina - 9)]
    params = navegacao + [
        ("fn", "search"), ("vid", "USP"), ("tab", "default_tab"), ("mode", "Basic"), ("srt", "rank"),
        ("vl(freeText0)", "a"),  # a busca não aceita termo vazio; "a" é um termo bem genérico
        ("fctN", "facet_library"), ("fctV", "ICMC"),
        ("fctN", "facet_rtype"), ("fctV", "books"),
        ("fctN", "facet_creationdate"), ("fctV", periodo),
    ]
    html = sessao.get(BASE + "search.do", params=params, timeout=60).text
    total = re.search(r"EXLResultsNumbers.*?<em>\s*([\d.]+)\s*</em>", html, re.S)
    ids = list(dict.fromkeys(re.findall(r"doc=(\w+)", html)))
    return (int(total.group(1).replace(".", "")) if total else 0), ids


def buscar_ids(periodo):
    """Todos os IDs de livros de um período, percorrendo as páginas de resultado."""
    total, ids = buscar_pagina(periodo, 0)
    time.sleep(PAUSA)
    for pagina in range(1, (min(total, LIMITE) + 9) // 10):
        ids += buscar_pagina(periodo, pagina)[1]
        time.sleep(PAUSA)
    aviso = "  <- ACIMA DO LIMITE, alguns livros ficaram de fora" if total > LIMITE else ""
    print(f"{periodo}: {total} livros{aviso}")
    return ids


def baixar_pnx(doc):
    """Baixa (ou lê do cache) o XML completo de um registro."""
    arquivo = os.path.join(PASTA, "pnx", doc + ".xml")
    if not os.path.exists(arquivo):
        r = sessao.get(BASE + "display.do", params={"doc": doc, "vid": "USP", "showPnx": "true"}, timeout=60)
        if not r.text.lstrip().startswith("<?xml"):
            raise ValueError("resposta não é XML")
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write(r.text)
        time.sleep(PAUSA)
    return ET.parse(arquivo).getroot()


def campo(raiz, caminho):
    """Lista com os textos de um campo do XML, ex.: campo(raiz, 'display/title')."""
    secao, nome = caminho.split("/")
    # re.sub remove o destaque <span class="searchword"> que o site insere em volta do termo buscado
    return [re.sub(r"<[^>]+>", "", e.text).strip() for e in raiz.findall(f"p:{secao}/p:{nome}", NS) if e.text]


def extrair(doc, raiz):
    """Transforma o XML de um livro em uma linha da tabela."""
    # Cada exemplar vem como "$$LICMC$$2(nº de chamada)$$S(situação)$$3(qtde)$$4(indisponíveis)$$6(...)"
    exemplares = [dict(re.findall(r"\$\$(\w)([^$]*)", a)) for a in campo(raiz, "display/availlibrary")]
    icmc = [e for e in exemplares if e.get("L") == "ICMC"]
    # Registros "PROD-..." são cópias da produção intelectual; preferimos o nº de chamada do acervo
    chamadas = [e.get("2", "").strip("() ") for e in icmc]
    chamada = next((c for c in chamadas if not c.startswith("PROD")), chamadas[0] if chamadas else "")
    paginas = re.search(r"(\d+)\s*p", " ".join(campo(raiz, "display/format")))
    return {
        "id": doc,
        "titulo": " | ".join(campo(raiz, "display/title")),
        "autores": " | ".join(campo(raiz, "display/creator") + campo(raiz, "display/contributor")),
        "ano": " | ".join(campo(raiz, "display/creationdate")),
        "editora": " | ".join(campo(raiz, "addata/pub")),
        "paginas": paginas.group(1) if paginas else "",
        "idioma": " | ".join(campo(raiz, "display/language")),
        "assuntos": " | ".join(campo(raiz, "search/subject")),
        "isbn": " | ".join(campo(raiz, "search/isbn")),
        "bibliotecas_usp": " | ".join(campo(raiz, "facets/library")),
        "chamada_icmc": chamada,
        "exemplares_icmc": sum(int(e.get("3", 0) or 0) for e in icmc),
        "indisponiveis_icmc": sum(int(e.get("4", 0) or 0) for e in icmc),
        "campo6_icmc": sum(int(e.get("6", 0) or 0) for e in icmc),  # possivelmente nº de empréstimos (a confirmar)
        "dedalus_doc": " | ".join(campo(raiz, "search/lsr10")),
    }


def main():
    os.makedirs(os.path.join(PASTA, "pnx"), exist_ok=True)

    if len(sys.argv) == 3:
        periodos = [f"[{ano} TO {ano}]" for ano in range(int(sys.argv[1]), int(sys.argv[2]) + 1)]
    else:
        periodos = ["[-999999999 TO 1899]"] + [f"[{ano} TO {ano}]" for ano in range(1900, time.localtime().tm_year + 1)]

    ids = []
    for periodo in periodos:
        ids += buscar_ids(periodo)
    ids = list(dict.fromkeys(ids))

    livros = []
    for i, doc in enumerate(ids, 1):
        try:
            livros.append(extrair(doc, baixar_pnx(doc)))
        except Exception as erro:
            print(f"\n  erro em {doc}: {erro}")
        print(f"\rregistros: {i}/{len(ids)}", end="", flush=True)

    saida = os.path.join(PASTA, "livros_icmc.csv")
    with open(saida, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=livros[0].keys())
        escritor.writeheader()
        escritor.writerows(livros)
    print(f"\n{len(livros)} livros salvos em {os.path.abspath(saida)}")


if __name__ == "__main__":
    main()
