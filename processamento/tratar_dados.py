"""
Trata os dados brutos da coleta (dados/livros_icmc.csv) e gera dados/livros_tratados.csv,
o arquivo usado pelas visualizações.

Passos:
  1. Tira o que não é livro: capítulos e artigos (páginas em intervalo, ex.: "p. 303-346").
  2. Tira livros repetidos: a cópia da produção intelectual (nº de chamada PROD-...) quando o mesmo
     livro já está no acervo.
  3. Ano: o primeiro ano de 4 dígitos ("c2015" -> 2015). Livros sem ano saem.
  4. País de publicação: pelo código MARC do registro (bl = Brasil); se vazio ou inválido, pela cidade.
  5. Gênero: pelas palavras-chave dos assuntos.
  6. Idioma: código -> nome ("por" -> "Português").

Uso: python tratar_dados.py
"""
import os
import re

import pandas as pd

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados")

# Códigos MARC de país (lista oficial: https://www.loc.gov/marc/countries/) -> (nome, código ISO usado no mapa)
PAISES = {
    "bl": ("Brasil", "BRA"), "ag": ("Argentina", "ARG"), "cl": ("Chile", "CHL"), "mx": ("México", "MEX"),
    "ck": ("Colômbia", "COL"), "pe": ("Peru", "PER"), "uy": ("Uruguai", "URY"), "cu": ("Cuba", "CUB"),
    "at": ("Austrália", "AUS"), "nz": ("Nova Zelândia", "NZL"), "gw": ("Alemanha", "DEU"), "sz": ("Suíça", "CHE"),
    "ne": ("Países Baixos", "NLD"), "fr": ("França", "FRA"), "it": ("Itália", "ITA"), "sp": ("Espanha", "ESP"),
    "po": ("Portugal", "PRT"), "be": ("Bélgica", "BEL"), "au": ("Áustria", "AUT"), "dk": ("Dinamarca", "DNK"),
    "sw": ("Suécia", "SWE"), "no": ("Noruega", "NOR"), "fi": ("Finlândia", "FIN"), "pl": ("Polônia", "POL"),
    "hu": ("Hungria", "HUN"), "ie": ("Irlanda", "IRL"), "ru": ("Rússia", "RUS"), "ja": ("Japão", "JPN"),
    "cc": ("China", "CHN"), "ch": ("Taiwan", "TWN"), "ko": ("Coreia do Sul", "KOR"), "ii": ("Índia", "IND"),
    "si": ("Singapura", "SGP"), "is": ("Israel", "ISR"), "sa": ("África do Sul", "ZAF"), "vm": ("Vietnã", "VNM"),
}
# Códigos de 3 letras são estados/províncias; a última letra diz o país (ex.: nyu = Nova York, EUA)
SUFIXOS = {"u": ("Estados Unidos", "USA"), "c": ("Canadá", "CAN"), "k": ("Reino Unido", "GBR"), "a": ("Austrália", "AUS")}

# Gênero = primeiro grupo cujas palavras-chave aparecem no assunto principal; se nenhum aparecer, olhamos
# todos os assuntos. A ordem importa: "EDUCAÇÃO MATEMÁTICA" fica em Educação, que vem antes de Matemática.
GENEROS = {
    "Computação": ["COMPUTAÇÃO", "COMPUTADOR", "PROGRAMAÇÃO", "SOFTWARE", "INTELIGÊNCIA ARTIFICIAL",
                   "SISTEMAS OPERACIONAIS", "PYTHON", "JAVA", "ALGORITMO", "BANCO DE DADOS", "REDES",
                   "PROCESSAMENTO DE IMAGENS", "ROBÓTICA", "INTERNET", "JOGOS", "MINERAÇÃO DE DADOS",
                   "APRENDIZADO", "RECONHECIMENTO DE PADRÕES", "CIÊNCIA DE DADOS"],
    "Estatística": ["ESTATÍSTICA", "PROBABILIDADE", "SÉRIES TEMPORAIS", "ECONOMETRIA"],
    "Educação": ["EDUCAÇÃO", "ENSINO", "PROFESSORES", "ESCOLA", "APRENDIZAGEM"],
    "Matemática": ["MATEMÁTICA", "ÁLGEBRA", "EQUAÇÕES", "GEOMETRIA", "CÁLCULO", "TOPOLOGIA", "LÓGICA",
                   "NÚMEROS", "ANÁLISE NUMÉRICA", "ANÁLISE MATEMÁTICA", "ANÁLISE REAL", "ANÁLISE FUNCIONAL"],
    "Literatura": ["LITERATURA", "FICÇÃO", "ROMANCE", "CONTOS", "POESIA"],
    "História e biografias": ["HISTÓRIA", "BIOGRAFIA", "CIENTISTAS"],
}

IDIOMAS = {"por": "Português", "eng": "Inglês", "spa": "Espanhol", "fre": "Francês", "ger": "Alemão",
           "ita": "Italiano", "rus": "Russo", "jpn": "Japonês", "chi": "Chinês"}


def eh_capitulo(paginas):
    """'p. 303-346.' (intervalo de páginas) = capítulo ou artigo; '438 p.' (total) = livro."""
    return re.search(r"\d+\s*-\s*\d+", paginas) is not None


def pais_do_codigo(codigo):
    """'bl' -> 'Brasil'; 'nyu' -> 'Estados Unidos'; vazio ou desconhecido -> ''."""
    codigo = codigo.split("|")[0].strip()
    if len(codigo) == 3 and codigo[-1] in SUFIXOS:
        return SUFIXOS[codigo[-1]][0]
    return PAISES.get(codigo, ("", ""))[0]


def cidade(local):
    """'Cham (ZG), Switzerland' -> 'cham'; 'São Paulo, SP' -> 'são paulo'."""
    return local.split("|")[0].split(",")[0].split("(")[0].strip().lower()


def genero(assuntos):
    """Gênero pelas palavras-chave: primeiro no assunto principal, depois em todos os assuntos."""
    # O que está entre parênteses são subdivisões, não o assunto: "CÁLCULO (ESTUDO E ENSINO)" -> "CÁLCULO"
    lista = [re.sub(r"\(.*?\)", "", a).upper() for a in assuntos.split("|")]
    for candidatos in (lista[:1], lista):
        for nome, palavras_chave in GENEROS.items():
            if any(chave in assunto for assunto in candidatos for chave in palavras_chave):
                return nome
    return "Outros"


livros = pd.read_csv(os.path.join(PASTA, "livros_icmc.csv"), dtype=str).fillna("")
print(f"registros coletados: {len(livros)}")

# 1. Capítulos e artigos não são livros
capitulos = livros["paginas"].map(eh_capitulo)
livros = livros[~capitulos]
print(f"1. capítulos e artigos removidos: {capitulos.sum()}")

# 2. Cópia da produção intelectual (PROD-...) de um livro que já está no acervo
titulo = livros["titulo"].str.lower().str.replace(r"\W+", " ", regex=True).str.strip()
producao = livros["chamada_icmc"].str.startswith("PROD")
repetidos = producao & titulo.isin(set(titulo[~producao]))
livros = livros[~repetidos]
print(f"2. cópias repetidas da produção intelectual removidas: {repetidos.sum()}")

# 3. Ano
livros["ano"] = pd.to_numeric(livros["ano"].str.extract(r"(\d{4})")[0], errors="coerce")
sem_ano = livros["ano"].isna()
livros = livros[~sem_ano].copy()
livros["ano"] = livros["ano"].astype(int)
print(f"3. livros sem ano removidos: {sem_ano.sum()}")

# 4. País: pelo código MARC; quem ficar sem país recebe o país mais comum dos livros da mesma cidade
livros["pais"] = livros["codigo_pais_marc"].map(pais_do_codigo)
livros["cidade"] = livros["local_publicacao"].map(cidade)
com_pais = livros[livros["pais"] != ""]
pais_da_cidade = com_pais.groupby("cidade")["pais"].agg(lambda paises: paises.value_counts().index[0])
sem_pais = livros["pais"] == ""
livros.loc[sem_pais, "pais"] = livros.loc[sem_pais, "cidade"].map(pais_da_cidade).fillna("")
codigo_iso = {nome: iso for nome, iso in list(PAISES.values()) + list(SUFIXOS.values())}
livros["pais_iso3"] = livros["pais"].map(codigo_iso).fillna("")
print(f"4. país pelo código MARC: {len(livros) - sem_pais.sum()} | pela cidade: "
      f"{(sem_pais & (livros['pais'] != '')).sum()} | sem país: {(livros['pais'] == '').sum()}")

# 5. Gênero
livros["genero"] = livros["assuntos"].map(genero)
print(f"5. gêneros: {livros['genero'].value_counts().to_dict()}")

# 6. Idioma
livros["idioma"] = livros["idioma"].str.split(";").str[0].str.strip().map(lambda i: IDIOMAS.get(i, i))

livros = livros.rename(columns={"exemplares_icmc": "exemplares", "emprestimos_icmc": "emprestimos"})
colunas = ["id", "titulo", "autores", "ano", "genero", "assuntos", "pais", "pais_iso3", "local_publicacao",
           "editora", "idioma", "isbn", "chamada_icmc", "exemplares", "emprestimos"]
livros[colunas].to_csv(os.path.join(PASTA, "livros_tratados.csv"), index=False)
print(f"{len(livros)} livros salvos em dados/livros_tratados.csv")
