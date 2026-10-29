"""
Coleta livros da Biblioteca do ICMC pela Busca Integrada da USP (Primo).

Fluxo:
  1. Para cada ano de publicação, faz a busca filtrada (Biblioteca = ICMC, Tipo = Livros, Ano = ano)
     e anota os IDs dos registros. A busca é feita ano a ano porque o site só deixa paginar
     até ~490 resultados por busca.
  2. Para cada ID, baixa o registro completo em XML (PNX) e extrai os campos.
  3. Salva tudo em dados/livros_icmc.csv.

Os períodos e os XMLs são processados com até quatro trabalhadores. Cada busca
tem sua própria sessão e paginação sequencial. Há uma pausa global de 1 segundo
entre o início das requisições, e os XMLs válidos são reutilizados do cache.
O Dedalus não é acessado.

Limites: o site exige um termo de busca; usamos "a", que não garante encontrar
todo o catálogo. Resultados acima do limite de paginação geram um aviso.
Se alguma busca ou registro falhar, o CSV anterior é preservado; execute
novamente para aproveitar os XMLs que já foram baixados.

Uso:
  python coleta/coletar_livros_icmc.py                    # todos os anos
  python coleta/coletar_livros_icmc.py 2015 2016          # de 2015 a 2016
  python coleta/coletar_livros_icmc.py 2015 2016 --trabalhadores 4
  python coleta/coletar_livros_icmc.py 2015 2016 --trabalhadores 1  # sequencial
"""
import argparse
import csv
import io
import os
import re
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from threading import Lock, local

import requests

BASE = "https://www.buscaintegrada.usp.br/primo_library/libweb/action/"
PAUSA = 1  # intervalo global entre o início das requisições, mesmo em paralelo
TRABALHADORES = 4
LIMITE = 490  # o site não deixa paginar além de ~490 resultados por busca
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados")
NS = {"p": "http://www.exlibrisgroup.com/xsd/primo/primo_nm_bib"}
USER_AGENT = "Projeto academico SCC0252 Visualizacao Computacional ICMC-USP"

por_thread = local()
controle_requisicoes = Lock()
proxima_requisicao = 0


def criar_sessao():
    sessao = requests.Session()
    sessao.headers["User-Agent"] = USER_AGENT
    return sessao


def aguardar_requisicao():
    """Compartilha a pausa entre os trabalhadores sem esperar a resposta anterior."""
    global proxima_requisicao
    while True:
        with controle_requisicoes:
            agora = time.monotonic()
            espera = proxima_requisicao - agora
            if espera <= 0:
                proxima_requisicao = agora + PAUSA
                return
        time.sleep(espera)


def adiar_requisicoes(espera):
    """Uma resposta de sobrecarga adia também as consultas dos outros trabalhadores."""
    global proxima_requisicao
    with controle_requisicoes:
        proxima_requisicao = max(proxima_requisicao, time.monotonic() + espera)


def requisitar(acao, parametros, sessao):
    """Valida o HTTP e repete até duas vezes em falhas temporárias."""
    for tentativa in range(3):
        aguardar_requisicao()
        try:
            resposta = sessao.get(BASE + acao, params=parametros, timeout=(10, 60))
            if resposta.status_code in {429, 500, 502, 503, 504}:
                aviso = resposta.headers.get("Retry-After", "")
                try:
                    espera = float(aviso)
                except ValueError:
                    try:
                        espera = parsedate_to_datetime(aviso).timestamp() - time.time()
                    except (ValueError, TypeError, OverflowError):
                        espera = 2 ** (tentativa + 1)
                adiar_requisicoes(max(1, espera))
                if tentativa < 2:
                    print(f"{acao}: HTTP {resposta.status_code}; tentando novamente.", flush=True)
                    continue
            resposta.raise_for_status()
            return resposta
        except (requests.Timeout, requests.ConnectionError):
            if tentativa == 2:
                raise
            adiar_requisicoes(2 ** (tentativa + 1))
            print(f"{acao}: falha de conexão; tentando novamente.", flush=True)


def buscar_pagina(periodo, pagina, sessao):
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
    html = requisitar("search.do", params, sessao).text
    total = re.search(r"EXLResultsNumbers.*?<em>\s*([\d.,\s]+)\s*</em>", html, re.S)
    if total is None:
        raise ValueError(f"{periodo}, página {pagina + 1}: total de resultados não reconhecido")
    total = int(re.sub(r"\D", "", total.group(1)))
    ids = list(dict.fromkeys(re.findall(r"\bdoc=([A-Za-z0-9_-]+)", html)))
    if total > 0 and not ids:
        raise ValueError(f"{periodo}, página {pagina + 1}: nenhum ID na página")
    return total, ids


def buscar_ids(periodo):
    """Todos os IDs de livros de um período, percorrendo as páginas de resultado."""
    # O Primo guarda a navegação em cookies: uma sessão exclusiva por período.
    with criar_sessao() as sessao:
        total, ids = buscar_pagina(periodo, 0, sessao)
        vistos = set(ids)
        for pagina in range(1, (min(total, LIMITE) + 9) // 10):
            _, pagina_ids = buscar_pagina(periodo, pagina, sessao)
            novos = [doc for doc in pagina_ids if doc not in vistos]
            if not novos:
                raise ValueError(f"{periodo}, página {pagina + 1}: paginação repetida")
            ids.extend(novos)
            vistos.update(novos)
    if len(ids) < min(total, LIMITE):
        raise ValueError(f"{periodo}: esperados {min(total, LIMITE)} IDs, recebidos {len(ids)}")
    aviso = "  <- ACIMA DO LIMITE, alguns livros ficaram de fora" if total > LIMITE else ""
    print(f"{periodo}: {len(ids)} IDs coletados de {total} resultados{aviso}", flush=True)
    return ids


def salvar_atomico(arquivo, conteudo):
    """Só substitui o arquivo depois de terminar a escrita."""
    os.makedirs(os.path.dirname(arquivo), exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(arquivo), delete=False) as f:
            temporario = f.name
            f.write(conteudo)
        os.replace(temporario, arquivo)
    finally:
        if temporario and os.path.exists(temporario):
            os.remove(temporario)


def validar_pnx(conteudo, doc):
    raiz = ET.fromstring(conteudo)
    if (raiz.tag != f"{{{NS['p']}}}record"
            or raiz.findtext("p:control/p:recordid", namespaces=NS) != doc):
        raise ValueError(f"PNX inválido ou de outro registro: {doc}")
    return raiz


def baixar_pnx(doc):
    """Baixa (ou lê do cache) o XML completo de um registro."""
    arquivo = os.path.join(PASTA, "pnx", doc + ".xml")
    if os.path.exists(arquivo):
        try:
            with open(arquivo, "rb") as f:
                return validar_pnx(f.read(), doc)
        except (ET.ParseError, ValueError):
            print(f"Cache inválido em {doc}; baixando novamente.", flush=True)
    # Os downloads reutilizam conexões, com uma sessão separada por trabalhador.
    if not hasattr(por_thread, "sessao"):
        por_thread.sessao = criar_sessao()
    resposta = requisitar("display.do", {"doc": doc, "vid": "USP", "showPnx": "true"}, por_thread.sessao)
    raiz = validar_pnx(resposta.content, doc)  # Não salva HTML nem XML incompleto no cache.
    salvar_atomico(arquivo, resposta.content)
    return raiz


def campo(raiz, caminho):
    """Lista com os textos de um campo do XML, ex.: campo(raiz, 'display/title')."""
    secao, nome = caminho.split("/")
    # re.sub remove o destaque <span class="searchword"> que o site insere em volta do termo buscado
    textos = [re.sub(r"<[^>]+>", "", "".join(e.itertext())).strip()
              for e in raiz.findall(f"p:{secao}/p:{nome}", NS)]
    return [texto for texto in textos if texto]


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


def coletar_livro(doc):
    try:
        return extrair(doc, baixar_pnx(doc))
    except (requests.RequestException, ET.ParseError, ValueError, OSError) as erro:
        print(f"Erro em {doc}: {erro}", flush=True)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ano_inicial", type=int, nargs="?")
    parser.add_argument("ano_final", type=int, nargs="?")
    parser.add_argument("--trabalhadores", type=int, default=TRABALHADORES, help="tarefas em paralelo (padrão: 4)")
    args = parser.parse_args()
    if (args.ano_inicial is None) != (args.ano_final is None):
        parser.error("informe os dois anos ou nenhum")
    if args.ano_inicial is not None and args.ano_inicial > args.ano_final:
        parser.error("o ano inicial deve ser menor ou igual ao final")
    if args.trabalhadores < 1:
        parser.error("--trabalhadores deve ser pelo menos 1")

    inicio = time.perf_counter()
    if args.ano_inicial is not None:
        periodos = [f"[{ano} TO {ano}]" for ano in range(args.ano_inicial, args.ano_final + 1)]
    else:
        periodos = ["[-999999999 TO 1899]"] + [f"[{ano} TO {ano}]" for ano in range(1900, time.localtime().tm_year + 1)]

    print(f"Buscando {len(periodos)} períodos com {args.trabalhadores} trabalhadores.", flush=True)
    with ThreadPoolExecutor(max_workers=args.trabalhadores) as executor:
        por_periodo = executor.map(buscar_ids, periodos)
        # map mantém a ordem dos períodos, mesmo quando as buscas terminam fora de ordem.
        ids = list(dict.fromkeys(doc for registros in por_periodo for doc in registros))
    if not ids:
        print("Nenhum registro encontrado; o CSV anterior foi preservado.")
        return

    livros = []
    with ThreadPoolExecutor(max_workers=args.trabalhadores) as executor:
        for i, livro in enumerate(executor.map(coletar_livro, ids), 1):
            if livro is not None:
                livros.append(livro)
            print(f"\rregistros processados: {i}/{len(ids)}", end="", flush=True)
    print()
    if len(livros) != len(ids):
        raise RuntimeError(f"{len(ids) - len(livros)} registros falharam; o CSV anterior foi preservado. "
                           "Execute novamente para aproveitar o cache.")

    saida = os.path.join(PASTA, "livros_icmc.csv")
    conteudo = io.StringIO(newline="")
    escritor = csv.DictWriter(conteudo, fieldnames=livros[0].keys())
    escritor.writeheader()
    escritor.writerows(livros)
    salvar_atomico(saida, conteudo.getvalue().encode("utf-8"))
    print(f"{len(livros)} livros salvos em {os.path.abspath(saida)}")
    print(f"Tempo total: {time.perf_counter() - inicio:.1f} segundos.")


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, ET.ParseError, ValueError, OSError, RuntimeError) as erro:
        print(f"Coleta interrompida: {erro}", file=sys.stderr)
        sys.exit(1)
