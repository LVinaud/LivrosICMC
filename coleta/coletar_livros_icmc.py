"""
Baixa os livros da Biblioteca do ICMC pela Busca Integrada da USP e salva em dados/livros_icmc.csv.

Como funciona:
  1. Para cada ano, pesquisa os livros do ICMC publicados naquele ano. O site mostra 10 livros por
     página e não deixa passar de ~490 resultados numa pesquisa, por isso pesquisamos ano a ano.
  2. Para cada livro encontrado, baixa o registro completo dele em XML (fica guardado em dados/pnx,
     então rodar de novo não baixa outra vez).
  3. Tira do XML os campos que interessam e salva tudo num CSV.

Uma requisição por vez, com pausa entre elas, para não sobrecarregar o site.
(O Dedalus não é usado: o robots.txt dele não permite programas.)

Uso: python coletar_livros_icmc.py 2015 2025      (ano inicial e ano final)
"""
import csv
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

SITE = "https://www.buscaintegrada.usp.br/primo_library/libweb/action/"
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados")
PAUSA = 2  # segundos entre uma requisição e outra
XML = "{http://www.exlibrisgroup.com/xsd/primo/primo_nm_bib}"  # prefixo das tags do XML do registro

sessao = requests.Session()
sessao.headers["User-Agent"] = "Projeto academico SCC0252 Visualizacao Computacional ICMC-USP"


def pesquisar(ano, pagina):
    """HTML de uma página de resultados com os livros do ICMC publicados no ano (pagina = 0, 1, 2...)."""
    parametros = {
        "fn": "search", "vid": "USP", "tab": "default_tab", "mode": "Basic", "srt": "rank",
        "vl(freeText0)": "a",  # a pesquisa precisa de um termo; "a" aparece em quase todo registro
        "fctN": ["facet_library", "facet_rtype", "facet_creationdate"],  # filtros: biblioteca, tipo, ano
        "fctV": ["ICMC", "books", f"[{ano} TO {ano}]"],
    }
    if pagina == 0:
        parametros["ct"] = "search"
    else:  # para ir à próxima página, o site usa o número do primeiro livro da página anterior
        parametros.update({"ct": "Next Page", "pag": "nxt", "indx": 10 * pagina - 9})
    return sessao.get(SITE + "search.do", params=parametros, timeout=60).text


def ids_dos_livros(ano):
    """Percorre as páginas de resultado do ano e devolve os ids dos livros."""
    html = pesquisar(ano, 0)
    achou = re.search(r"EXLResultsNumbers.*?<em>\s*([\d.]+)", html, re.S)  # "1.234 resultados"
    total = int(achou.group(1).replace(".", "")) if achou else 0
    ids = re.findall(r"doc=(\w+)", html)
    for pagina in range(1, (min(total, 490) + 9) // 10):
        time.sleep(PAUSA)
        ids += re.findall(r"doc=(\w+)", pesquisar(ano, pagina))
    print(f"{ano}: {total} livros")
    return ids


def baixar_registro(id_livro):
    """Registro completo do livro em XML (baixa só se ainda não estiver em dados/pnx)."""
    arquivo = os.path.join(PASTA, "pnx", id_livro + ".xml")
    if not os.path.exists(arquivo):
        resposta = sessao.get(SITE + "display.do", params={"doc": id_livro, "vid": "USP", "showPnx": "true"}, timeout=60)
        if not resposta.text.startswith("<?xml"):
            raise ValueError("a resposta não é um XML")
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write(resposta.text)
        time.sleep(PAUSA)
    return ET.parse(arquivo).getroot()


def campo(registro, caminho):
    """Lista com os textos de um campo do XML. Ex.: campo(registro, "display/title")"""
    secao, nome = caminho.split("/")
    # re.sub tira o destaque <span class="searchword"> que o site coloca em volta do termo pesquisado
    return [re.sub(r"<[^>]+>", "", e.text) for e in registro.findall(f"{XML}{secao}/{XML}{nome}") if e.text]


def texto(registro, caminho):
    """Os textos do campo juntos com " | " (alguns campos têm mais de um valor)."""
    return " | ".join(campo(registro, caminho))


def dados_do_icmc(registro):
    """Nº de chamada, exemplares e empréstimos na biblioteca do ICMC.
    Cada biblioteca vem num texto assim:  $$IUSP$$LICMC$$2(68N15 S572 e.2)$$Savailable$$32$$41$$5N$$67
    em que L = biblioteca, 2 = nº de chamada, 3 = nº de exemplares e 6 = nº de empréstimos."""
    chamada, exemplares, emprestimos = "", 0, 0
    for biblioteca in campo(registro, "display/availlibrary"):
        partes = {p[0]: p[1:] for p in biblioteca.split("$$") if p}  # "LICMC" -> partes["L"] = "ICMC"
        if partes.get("L") == "ICMC":
            exemplares += int(partes.get("3") or 0)
            emprestimos += int(partes.get("6") or 0)
            if chamada == "" or chamada.startswith("PROD"):  # PROD = produção intelectual do ICMC
                chamada = partes.get("2", "").strip("() ")
    return chamada, exemplares, emprestimos


def extrair(id_livro, registro):
    """Uma linha da tabela com os campos que interessam."""
    chamada, exemplares, emprestimos = dados_do_icmc(registro)
    return {
        "id": id_livro,
        "titulo": texto(registro, "display/title"),
        "autores": " | ".join(campo(registro, "display/creator") + campo(registro, "display/contributor")),
        "ano": texto(registro, "display/creationdate"),
        "editora": texto(registro, "addata/pub"),
        "local_publicacao": texto(registro, "addata/cop"),
        "codigo_pais_marc": texto(registro, "dedup/f8"),  # país de publicação, ex.: bl = Brasil
        "paginas": texto(registro, "display/format"),  # "438 p." (livro) ou "p. 303-346." (capítulo)
        "idioma": texto(registro, "display/language"),
        "assuntos": texto(registro, "search/subject"),
        "isbn": texto(registro, "search/isbn"),
        "chamada_icmc": chamada,
        "exemplares_icmc": exemplares,
        "emprestimos_icmc": emprestimos,
    }


def main():
    ano_inicial, ano_final = int(sys.argv[1]), int(sys.argv[2])
    os.makedirs(os.path.join(PASTA, "pnx"), exist_ok=True)

    ids = []
    for ano in range(ano_inicial, ano_final + 1):
        ids += ids_dos_livros(ano)
        time.sleep(PAUSA)
    ids = list(dict.fromkeys(ids))  # tira os repetidos (o mesmo livro pode aparecer em mais de um ano)

    livros = []
    for i, id_livro in enumerate(ids, 1):
        print(f"baixando registro {i}/{len(ids)}", end="\r")
        try:
            livros.append(extrair(id_livro, baixar_registro(id_livro)))
        except Exception as erro:
            print(f"\nerro no livro {id_livro}: {erro}")

    with open(os.path.join(PASTA, "livros_icmc.csv"), "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=livros[0].keys())
        escritor.writeheader()
        escritor.writerows(livros)
    print(f"\n{len(livros)} livros salvos em dados/livros_icmc.csv")


if __name__ == "__main__":
    main()
