"""
Carrega os livros e cria as colunas derivadas usadas pelas visualizações.

Entrada: dados/livros_icmc_paises.csv (gerado por processamento/pais_publicacao.py)
"""
import os
import re

import pandas as pd

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados")

# Gênero = primeiro grupo cujas palavras-chave aparecem no assunto principal do livro; se nenhum casar,
# olhamos todos os assuntos; se ainda assim nada casar, "Outros".
# A ordem importa: o primeiro que casar vence (ex.: "EDUCAÇÃO MATEMÁTICA" fica em Educação).
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
# Cada gênero tem sempre a mesma cor, em todos os gráficos. Nesta ordem, cores vizinhas
# (fatias da rosa, blocos empilhados) foram verificadas para continuar distinguíveis por daltônicos.
CORES = {"Computação": "#2a78d6", "Matemática": "#eb6834", "Educação": "#1baf7a", "Literatura": "#eda100",
         "História e biografias": "#e87ba4", "Estatística": "#008300", "Outros": "#a3a29c"}

IDIOMAS = {"por": "Português", "eng": "Inglês", "spa": "Espanhol", "fre": "Francês", "ger": "Alemão",
           "ita": "Italiano", "rus": "Russo", "jpn": "Japonês", "chi": "Chinês"}


def separar(texto):
    """Campos com vários valores vêm como 'A | B | C' -> ['A', 'B', 'C']"""
    return [parte.strip() for parte in texto.split("|") if parte.strip()]


def genero(assuntos):
    """Gênero do livro pelas palavras-chave de GENEROS: primeiro no assunto principal, depois em todos."""
    # O que está entre parênteses são subdivisões, não o assunto: "CÁLCULO (ESTUDO E ENSINO)" -> "CÁLCULO"
    lista = [re.sub(r"\(.*?\)", "", a) for a in separar(assuntos)]
    for candidatos in (lista[:1], lista):
        texto = " | ".join(candidatos).upper()
        for nome, chaves in GENEROS.items():
            if any(chave in texto for chave in chaves):
                return nome
    return "Outros"


def carregar():
    livros = pd.read_csv(os.path.join(PASTA, "livros_icmc_paises.csv"), dtype=str).fillna("")
    # "c2015", "2014 | 2012" -> 2015, 2014 (primeiro ano que aparece)
    livros["ano"] = pd.to_numeric(livros["ano"].str.extract(r"(\d{4})")[0], errors="coerce")
    livros["genero"] = livros["assuntos"].map(genero)
    livros["assunto_principal"] = livros["assuntos"].map(lambda a: (separar(a) or ["(sem assunto)"])[0])
    livros["idioma"] = livros["idioma"].str.split(r"[;|]").str[0].str.strip().map(lambda i: IDIOMAS.get(i, i or "?"))
    livros["paginas"] = pd.to_numeric(livros["paginas"], errors="coerce")
    livros["exemplares"] = pd.to_numeric(livros["exemplares_icmc"], errors="coerce").fillna(0).astype(int)
    livros["emprestimos"] = pd.to_numeric(livros["campo6_icmc"], errors="coerce").fillna(0).astype(int)
    livros["n_bibliotecas_usp"] = livros["bibliotecas_usp"].map(lambda b: len(separar(b)))
    return livros
