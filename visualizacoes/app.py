"""
App com as visualizações dos livros da Biblioteca do ICMC (entrega 1).

- Empréstimos: rosa (polar area) com os 5 livros mais emprestados de cada gênero.
- Origem: globo com o número de livros por país de publicação.
- Linha do tempo: livros publicados por ano e gênero.
- Clicar em um pedaço da rosa, em um país ou em uma barra lista os livros na tabela no fim da página.

Uso: python app.py   e abrir http://127.0.0.1:8050
"""
import pandas as pd
from dash import Dash, Input, Output, ctx, dash_table, dcc, html

import graficos
from dados import carregar

livros = carregar()

COLUNAS_TABELA = {"titulo": "Título", "autores": "Autores", "ano": "Ano", "genero": "Gênero", "pais": "País",
                  "idioma": "Idioma", "exemplares": "Exemplares", "emprestimos": "Empréstimos"}

app = Dash(__name__, title="Livros do ICMC")
app.layout = html.Div(style={"fontFamily": "sans-serif", "maxWidth": "1250px", "margin": "auto", "padding": "0 16px"}, children=[
    html.H1("Livros da Biblioteca do ICMC"),
    html.P(f"{len(livros)} livros publicados de {int(livros['ano'].min())} a {int(livros['ano'].max())}. "
           "Clique nos gráficos para listar os livros no fim da página."),

    dcc.Tabs(children=[
        dcc.Tab(label="Empréstimos", children=[
            html.H3("Quais livros são mais emprestados em cada gênero?"),
            html.P("Cada fatia é um gênero; dentro dela estão os 5 livros mais emprestados, do centro para fora "
                   "(tom mais escuro = mais emprestado). A área de cada pedaço é proporcional ao número de empréstimos."),
            dcc.Graph(id="rosa", figure=graficos.rosa_emprestimos(livros), config={"displayModeBar": False}),
        ]),
        dcc.Tab(label="Origem", children=[
            html.H3("De onde vem o acervo?"),
            html.P("Número de livros por país de publicação. Arraste para girar o globo."),
            dcc.Graph(id="globo", figure=graficos.globo(livros)),
        ]),
        dcc.Tab(label="Linha do tempo", children=[
            html.H3("Quantos livros de cada gênero foram publicados por ano?"),
            html.P("Clique em uma barra para ver os livros daquele gênero e ano."),
            dcc.Graph(id="linha", figure=graficos.linha_do_tempo(livros)),
        ]),
    ]),

    html.Div(style={"display": "flex", "alignItems": "center", "gap": "12px", "marginTop": "24px"}, children=[
        html.H3(id="titulo-tabela"),
        html.Button("Limpar seleção", id="limpar"),
    ]),
    dash_table.DataTable(
        id="tabela", columns=[{"id": c, "name": n} for c, n in COLUNAS_TABELA.items()],
        page_size=15, sort_action="native", filter_action="native",
        style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "fontFamily": "sans-serif"},
    ),
])


@app.callback(Output("titulo-tabela", "children"), Output("tabela", "data"),
              Input("rosa", "clickData"), Input("globo", "clickData"), Input("linha", "clickData"),
              Input("limpar", "n_clicks"))
def mostrar_tabela(clique_rosa, clique_globo, clique_linha, _):
    """Livros do último clique: pedaço da rosa (um livro), país ou barra (gênero + ano)."""
    origem = ctx.triggered_id
    if origem == "rosa" and clique_rosa:
        livro_id, titulo = clique_rosa["points"][0]["customdata"][:2]
        escolhidos, texto = livros[livros["id"] == livro_id], f"Livro: {titulo}"
    elif origem == "globo" and clique_globo:
        ponto = clique_globo["points"][0]
        escolhidos, texto = livros[livros["pais_iso3"] == ponto["location"]], f"País: {ponto['text']}"
    elif origem == "linha" and clique_linha:
        ponto = clique_linha["points"][0]
        genero, ano = ponto["customdata"], ponto["x"]
        escolhidos = livros[(livros["genero"] == genero) & (livros["ano"] == ano)]
        texto = f"{genero} publicados em {ano}"
    else:  # início ou "Limpar seleção"
        escolhidos, texto = livros, "Todos os livros"
    tabela = escolhidos[list(COLUNAS_TABELA)].sort_values("emprestimos", ascending=False)
    tabela["ano"] = tabela["ano"].map(lambda a: "" if pd.isna(a) else int(a))
    return f"{texto}: {len(tabela)} livro(s)", tabela.to_dict("records")


if __name__ == "__main__":
    app.run(debug=True)
