"""
App com as visualizações dos livros da Biblioteca do ICMC (entrega 1).

- Composição: treemap gênero -> assunto. Clicar em um retângulo (todos os livros, um gênero ou um
  assunto) muda a nuvem de palavras, que mostra as palavras mais comuns nos títulos daquele conjunto.
  Clicar em uma palavra lista os livros do conjunto que têm essa palavra no título.
- Uso: dispersão ano × empréstimos; clicar em um ponto mostra o livro.
- A tabela no fim da página lista os livros do último clique.

Uso: python app.py   e abrir http://127.0.0.1:8050
"""
import pandas as pd
from dash import Dash, Input, Output, ctx, dash_table, dcc, html

import graficos
from dados import carregar, palavras

livros = carregar()

COLUNAS_TABELA = {"titulo": "Título", "autores": "Autores", "ano": "Ano", "genero": "Gênero", "pais": "País",
                  "idioma": "Idioma", "exemplares": "Exemplares", "emprestimos": "Empréstimos"}
SEM_BARRA = {"displayModeBar": False}


def livros_do_conjunto(conjunto):
    """Livros do retângulo clicado no treemap: None = todos; {"genero"}; ou {"genero", "assunto"}."""
    if not conjunto:
        return livros
    escolhidos = livros[livros["genero"] == conjunto["genero"]]
    if conjunto.get("assunto"):
        escolhidos = escolhidos[escolhidos["assunto_treemap"] == conjunto["assunto"]]
    return escolhidos


def nome_do_conjunto(conjunto):
    if not conjunto:
        return "Todos os livros"
    return " › ".join(nome for nome in (conjunto["genero"], conjunto.get("assunto")) if nome)


app = Dash(__name__, title="Livros do ICMC")
app.layout = html.Div(style={"fontFamily": "sans-serif", "maxWidth": "1250px", "margin": "auto", "padding": "0 16px"}, children=[
    html.H1("Livros da Biblioteca do ICMC"),
    html.P(f"{len(livros)} livros. Clique nos gráficos para listar os livros no fim da página."),

    dcc.Tabs(children=[
        dcc.Tab(label="Composição", children=[
            html.H3("Do que é feito o acervo?"),
            html.P("Gênero → assunto principal (até 9 assuntos por gênero; o resto fica em \"Outros assuntos\"). "
                   "Clique em um gênero ou assunto: a nuvem abaixo mostra as palavras dos títulos daquele conjunto. "
                   "Para voltar a todos os livros, use \"Limpar seleção\" (no fim da página)."),
            dcc.Graph(id="treemap", config=SEM_BARRA),
            html.H4(id="titulo-nuvem"),
            dcc.Graph(id="nuvem", config=SEM_BARRA),
        ]),
        dcc.Tab(label="Uso", children=[
            html.H3("Quais livros são mais procurados?"),
            html.P("Cada ponto é um livro; o tamanho é o número de exemplares no ICMC. Livros no alto com pontos "
                   "pequenos são muito procurados e têm poucas cópias."),
            dcc.Graph(id="dispersao", figure=graficos.dispersao_uso(livros)),
        ]),
    ]),

    dcc.Store(id="conjunto"),
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


@app.callback(Output("conjunto", "data"), Input("treemap", "clickData"), Input("limpar", "n_clicks"),
              prevent_initial_call=True)
def escolher_conjunto(clique, _):
    """Retângulo clicado no treemap -> conjunto de livros ("Limpar seleção" volta para todos)."""
    if ctx.triggered_id == "limpar" or not clique:
        return None
    ponto = clique["points"][0]
    pai = ponto.get("parent", "")
    if pai == "":  # "Todos os livros"
        return None
    if pai == "Todos os livros":  # um gênero
        return {"genero": ponto["label"]}
    return {"genero": pai.split("/")[-1], "assunto": ponto["label"]}  # um assunto dentro do gênero


@app.callback(Output("treemap", "figure"), Output("titulo-nuvem", "children"), Output("nuvem", "figure"),
              Input("conjunto", "data"))
def mostrar_conjunto(conjunto):
    """Treemap aberto no conjunto escolhido + nuvem de palavras dos títulos desse conjunto."""
    return (graficos.treemap(livros, conjunto), f"Palavras nos títulos: {nome_do_conjunto(conjunto)}",
            graficos.nuvem(livros_do_conjunto(conjunto)["titulo"]))


@app.callback(Output("titulo-tabela", "children"), Output("tabela", "data"),
              Input("conjunto", "data"), Input("nuvem", "clickData"), Input("dispersao", "clickData"),
              Input("limpar", "n_clicks"))
def mostrar_tabela(conjunto, clique_nuvem, clique_dispersao, _):
    """Livros do último clique: retângulo do treemap, palavra da nuvem ou ponto da dispersão."""
    origem = ctx.triggered_id
    if origem == "nuvem" and clique_nuvem:
        palavra = clique_nuvem["points"][0]["customdata"][0]
        escolhidos = livros_do_conjunto(conjunto)
        escolhidos = escolhidos[escolhidos["titulo"].map(lambda t: palavra in palavras(t))]
        texto = f'{nome_do_conjunto(conjunto)} › palavra "{palavra}"'
    elif origem == "dispersao" and clique_dispersao:
        livro_id, titulo = clique_dispersao["points"][0]["customdata"][:2]
        escolhidos, texto = livros[livros["id"] == livro_id], f"Livro: {titulo}"
    elif origem == "limpar":
        escolhidos, texto = livros, "Todos os livros"
    else:  # início ou clique no treemap
        escolhidos, texto = livros_do_conjunto(conjunto), nome_do_conjunto(conjunto)
    tabela = escolhidos[list(COLUNAS_TABELA)].copy()
    tabela["ano"] = tabela["ano"].map(lambda a: "" if pd.isna(a) else int(a))
    return f"{texto}: {len(tabela)} livro(s)", tabela.to_dict("records")


if __name__ == "__main__":
    app.run(debug=True)
