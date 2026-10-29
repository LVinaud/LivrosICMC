"""
Descobre o país de publicação de cada livro.

O registro do catálogo da USP traz o código MARC do país de publicação (campo 008 do MARC,
que aparece no XML da Busca Integrada como dedup/f8), preenchido pelo bibliotecário.
Ex.: bl = Brasil, sz = Suíça, nyu = estado de Nova York (EUA).
Lista oficial dos códigos: https://www.loc.gov/marc/countries/

Quando o código está vazio, usamos a cidade de publicação: olhamos os outros livros da mesma
cidade que têm código e usamos o país mais comum entre eles.

Entrada: dados/livros_icmc.csv   Saída: dados/livros_icmc_paises.csv
Uso: python pais_publicacao.py
"""
import csv
import os
from collections import Counter, defaultdict

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados")

# Códigos MARC de 2 letras (países) -> (nome, código ISO de 3 letras, usado pelo mapa)
PAISES = {
    "bl": ("Brasil", "BRA"), "ag": ("Argentina", "ARG"), "cl": ("Chile", "CHL"), "mx": ("México", "MEX"),
    "ck": ("Colômbia", "COL"), "pe": ("Peru", "PER"), "uy": ("Uruguai", "URY"), "ve": ("Venezuela", "VEN"),
    "cu": ("Cuba", "CUB"), "at": ("Austrália", "AUS"), "nz": ("Nova Zelândia", "NZL"),
    "gw": ("Alemanha", "DEU"), "sz": ("Suíça", "CHE"), "ne": ("Países Baixos", "NLD"), "fr": ("França", "FRA"),
    "it": ("Itália", "ITA"), "sp": ("Espanha", "ESP"), "po": ("Portugal", "PRT"), "be": ("Bélgica", "BEL"),
    "au": ("Áustria", "AUT"), "dk": ("Dinamarca", "DNK"), "sw": ("Suécia", "SWE"), "no": ("Noruega", "NOR"),
    "fi": ("Finlândia", "FIN"), "pl": ("Polônia", "POL"), "xr": ("República Tcheca", "CZE"),
    "hu": ("Hungria", "HUN"), "gr": ("Grécia", "GRC"), "ie": ("Irlanda", "IRL"), "ru": ("Rússia", "RUS"),
    "ur": ("União Soviética", "RUS"), "rm": ("Romênia", "ROU"), "ja": ("Japão", "JPN"), "cc": ("China", "CHN"),
    "ch": ("Taiwan", "TWN"), "ko": ("Coreia do Sul", "KOR"), "ii": ("Índia", "IND"), "si": ("Singapura", "SGP"),
    "is": ("Israel", "ISR"), "tu": ("Turquia", "TUR"), "ir": ("Irã", "IRN"), "sa": ("África do Sul", "ZAF"),
    "vm": ("Vietnã", "VNM"),
}
# Códigos de 3 letras são estados/províncias; a última letra indica o país (ex.: nyu, cau, onc, enk)
SUFIXOS = {"u": ("Estados Unidos", "USA"), "c": ("Canadá", "CAN"), "k": ("Reino Unido", "GBR"), "a": ("Austrália", "AUS")}


def pais_do_codigo(codigo):
    """Converte o código MARC em (nome, ISO); ("", "") se vazio, 'xx' (sem local) ou desconhecido."""
    codigo = codigo.strip()
    if len(codigo) == 3 and codigo[-1] in SUFIXOS:
        return SUFIXOS[codigo[-1]]
    return PAISES.get(codigo, ("", ""))


def limpar_cidade(local):
    """Deixa só o nome da cidade: 'Cham (ZG), Switzerland' -> 'cham'; 'São Paulo, SP' -> 'são paulo'."""
    return local.split("|")[0].split(",")[0].split("(")[0].strip().lower()


def main():
    with open(os.path.join(PASTA, "livros_icmc.csv"), encoding="utf-8") as f:
        livros = list(csv.DictReader(f))

    # 1) País pelo código MARC
    for livro in livros:
        codigo = livro["codigo_pais_marc"].split("|")[0].strip()
        livro["pais"], livro["pais_iso3"] = pais_do_codigo(codigo)
        livro["fonte_pais"] = "código MARC" if livro["pais"] else ""
        if codigo and codigo != "xx" and not livro["pais"]:
            print(f"código desconhecido: '{codigo}' ({livro['local_publicacao']}) -> acrescentar em PAISES")

    # 2) Para quem ficou sem país: país mais comum entre os livros da mesma cidade
    paises_da_cidade = defaultdict(Counter)
    for livro in livros:
        if livro["pais"]:
            paises_da_cidade[limpar_cidade(livro["local_publicacao"])][(livro["pais"], livro["pais_iso3"])] += 1
    for livro in livros:
        cidade = limpar_cidade(livro["local_publicacao"])
        if not livro["pais"] and paises_da_cidade[cidade]:
            livro["pais"], livro["pais_iso3"] = paises_da_cidade[cidade].most_common(1)[0][0]
            livro["fonte_pais"] = "cidade"

    with open(os.path.join(PASTA, "livros_icmc_paises.csv"), "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=livros[0].keys())
        escritor.writeheader()
        escritor.writerows(livros)

    # Tabela para conferência: cidade, código e país encontrado
    print("\nlivros | cidade -> código -> país (fonte)")
    combinacoes = Counter((l["local_publicacao"], l["codigo_pais_marc"], l["pais"] or "DESCONHECIDO", l["fonte_pais"]) for l in livros)
    for (cidade, codigo, pais, fonte), n in combinacoes.most_common():
        print(f"{n:6d} | {cidade} -> {codigo or '(vazio)'} -> {pais} ({fonte or '-'})")
    print("\npaíses:", Counter(l["pais"] or "DESCONHECIDO" for l in livros).most_common())


if __name__ == "__main__":
    main()
