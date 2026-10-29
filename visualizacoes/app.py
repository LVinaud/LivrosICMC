"""
App com as visualizações dos livros da Biblioteca do ICMC (entrega 2: visões coordenadas).

- No topo, o filtro de anos: arrastar sobre o histograma (linking + brushing) ou usar o controle
  deslizante logo abaixo (consulta dinâmica). Ele vale para todos os gráficos.
- Composição: treemap gênero -> assunto. Clicar em um gênero ou assunto muda a nuvem de palavras,
  que mostra as palavras mais comuns nos títulos daquele conjunto.
- Origem (globo e idiomas), Relações (rede de assuntos) e Uso (dispersão ano × empréstimos).
- Clicar em uma palavra, país, idioma, assunto ou ponto lista os livros na tabela no fim da página.

Uso: python app.py   e abrir http://127.0.0.1:8050
"""
import pandas as pd
from dash import Dash, Input, Output, ctx, dash_table, dcc, html, no_update

import graficos
from dados import carregar, palavras, separar

livros = carregar()
ANO_MIN, ANO_MAX = int(livros["ano"].min()), int(livros["ano"].max())
passo = 1 if ANO_MAX - ANO_MIN <= 12 else 5 if ANO_MAX - ANO_MIN <= 60 else 10
marcas = {a: str(a) for a in range(ANO_MIN, ANO_MAX + 1) if a % passo == 0 or a in (ANO_MIN, ANO_MAX)}

COLUNAS_TABELA = {"titulo": "Título", "autores": "Autores", "ano": "Ano", "genero": "Gênero", "pais": "País",
                  "idioma": "Idioma", "exemplares": "Exemplares", "emprestimos": "Empréstimos"}
SEM_BARRA = {"displayModeBar": False}
lado_a_lado = {"display": "flex", "gap": "24px", "flexWrap": "wrap", "alignItems": "flex-start"}


def filtrar_anos(tabela, anos):
    return tabela[tabela["ano"].between(anos[0], anos[1])]


def livros_do_conjunto(tabela, conjunto):
    """Livros do retângulo clicado no treemap: None = todos; {"genero"}; ou {"genero", "assunto"}."""
    if not conjunto:
        return tabela
    escolhidos = tabela[tabela["genero"] == conjunto["genero"]]
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
    html.P(f"{len(livros)} livros. Escolha os anos de publicação arrastando sobre o histograma ou no controle "
           "abaixo dele: todos os gráficos seguem essa escolha. Clique nos gráficos para listar os livros no fim da página."),
    dcc.Graph(id="histograma", config=SEM_BARRA),
    dcc.RangeSlider(id="anos", min=ANO_MIN, max=ANO_MAX, step=1, value=[ANO_MIN, ANO_MAX], marks=marcas,
                    tooltip={"placement": "bottom"}),

    dcc.Tabs(style={"marginTop": "16px"}, children=[
        dcc.Tab(label="Composição", children=[
            html.H3("Do que é feito o acervo?"),
            html.P("Gênero → assunto principal (até 9 assuntos por gênero; o resto fica em \"Outros assuntos\"). "
                   "Clique em um gênero ou assunto: a nuvem abaixo mostra as palavras dos títulos daquele conjunto. "
                   "Para voltar a todos os livros, use \"Limpar seleção\" (no fim da página)."),
            dcc.Graph(id="treemap", config=SEM_BARRA),
            html.H4(id="titulo-nuvem"),
            dcc.Graph(id="nuvem", config=SEM_BARRA),
        ]),
        dcc.Tab(label="Origem", children=[
            html.H3("De onde vem o acervo?"),
            html.P("País de publicação (arraste para girar o globo) e idioma dos livros."),
            html.Div(style=lado_a_lado, children=[
                dcc.Graph(id="globo", style={"flex": "2 1 520px", "minWidth": 0}),
                dcc.Graph(id="idiomas", config=SEM_BARRA, style={"flex": "1 1 300px", "minWidth": 0}),
            ]),
        ]),
        dcc.Tab(label="Relações", children=[
            html.H3("Quais assuntos andam juntos?"),
            html.P("Cada círculo é um assunto (tamanho = nº de livros, cor = gênero, como no treemap); uma linha liga "
                   "dois assuntos que aparecem no mesmo livro. Só entram assuntos de 2 ou mais livros."),
            dcc.Graph(id="rede"),
        ]),
        dcc.Tab(label="Uso", children=[
            html.H3("Quais livros são mais procurados?"),
            html.P("Cada ponto é um livro; o tamanho é o número de exemplares no ICMC. Livros no alto com pontos "
                   "pequenos são muito procurados e têm poucas cópias."),
            dcc.Graph(id="dispersao"),
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


@app.callback(Output("anos", "value"), Input("histograma", "selectedData"), prevent_initial_call=True)
def selecionar_anos_no_histograma(selecionado):
    """Linking + brushing: o intervalo arrastado no histograma vira o filtro de anos."""
    if not selecionado or not selecionado.get("points"):
        return no_update
    anos = [p["x"] for p in selecionado["points"]]
    return [int(min(anos)), int(max(anos))]


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


@app.callback(
    Output("histograma", "figure"), Output("treemap", "figure"), Output("titulo-nuvem", "children"),
    Output("nuvem", "figure"), Output("globo", "figure"), Output("idiomas", "figure"),
    Output("rede", "figure"), Output("dispersao", "figure"),
    Input("anos", "value"), Input("conjunto", "data"),
)
def atualizar_graficos(anos, conjunto):
    """Redesenha os gráficos só com os livros dos anos escolhidos (e o treemap/nuvem no conjunto escolhido)."""
    escolhidos = filtrar_anos(livros, anos)
    return (graficos.histograma_anos(livros, anos), graficos.treemap(escolhidos, conjunto),
            f"Palavras nos títulos: {nome_do_conjunto(conjunto)}",
            graficos.nuvem(livros_do_conjunto(escolhidos, conjunto)["titulo"]),
            graficos.globo(escolhidos), graficos.idiomas(escolhidos),
            graficos.rede_assuntos(escolhidos), graficos.dispersao_uso(escolhidos))


@app.callback(
    Output("titulo-tabela", "children"), Output("tabela", "data"),
    Input("conjunto", "data"), Input("nuvem", "clickData"), Input("globo", "clickData"),
    Input("idiomas", "clickData"), Input("rede", "clickData"), Input("dispersao", "clickData"),
    Input("limpar", "n_clicks"), Input("anos", "value"),
)
def mostrar_tabela(conjunto, nuvem, globo, idiomas, rede, dispersao, _, anos):
    """Livros dos anos escolhidos e do último clique (retângulo, palavra, país, idioma, assunto ou ponto)."""
    origem = ctx.triggered_id
    escolhidos = filtrar_anos(livros, anos)
    if origem == "nuvem" and nuvem:
        palavra = nuvem["points"][0]["customdata"][0]
        escolhidos = livros_do_conjunto(escolhidos, conjunto)
        escolhidos = escolhidos[escolhidos["titulo"].map(lambda t: palavra in palavras(t))]
        texto = f'{nome_do_conjunto(conjunto)} › palavra "{palavra}"'
    elif origem == "globo" and globo:
        ponto = globo["points"][0]
        escolhidos, texto = escolhidos[escolhidos["pais_iso3"] == ponto["location"]], f"País: {ponto['text']}"
    elif origem == "idiomas" and idiomas:
        idioma = idiomas["points"][0]["y"]
        escolhidos, texto = escolhidos[escolhidos["idioma"] == idioma], f"Idioma: {idioma}"
    elif origem == "rede" and rede:
        assunto = rede["points"][0]["customdata"][0]
        escolhidos = escolhidos[escolhidos["assuntos"].map(lambda a: assunto in separar(a))]
        texto = f"Assunto: {assunto}"
    elif origem == "dispersao" and dispersao:
        livro_id, titulo = dispersao["points"][0]["customdata"][:2]
        escolhidos, texto = escolhidos[escolhidos["id"] == livro_id], f"Livro: {titulo}"
    elif origem == "limpar":
        texto = "Todos os livros"
    else:  # início, clique no treemap ou mudança nos anos
        escolhidos, texto = livros_do_conjunto(escolhidos, conjunto), nome_do_conjunto(conjunto)
    tabela = escolhidos[list(COLUNAS_TABELA)].copy()
    tabela["ano"] = tabela["ano"].map(lambda a: "" if pd.isna(a) else int(a))
    return f"{texto}: {len(tabela)} livro(s) de {anos[0]} a {anos[1]}", tabela.to_dict("records")


if __name__ == "__main__":
    app.run(debug=True)
