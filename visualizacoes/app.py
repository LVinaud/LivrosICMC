"""
App com as visualizações dos livros da Biblioteca do ICMC (entrega 2: visões coordenadas).

- No topo, o filtro de anos: arrastar sobre o histograma (linking + brushing) ou usar o controle
  deslizante logo abaixo (consulta dinâmica). Ele vale para todos os gráficos.
- Cada aba responde a uma pergunta sobre o acervo.
- Clicar em um retângulo, fatia, palavra, barra, país, idioma, assunto ou ponto lista os livros
  correspondentes na tabela no fim da página.

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


def filtrar_selecao(tabela, selecao):
    """Aplica o último clique (guardado em dcc.Store "selecao") à tabela de livros."""
    tipo, valor = selecao["tipo"], selecao["valor"]
    if tipo == "genero":
        return tabela[tabela["genero"] == valor]
    if tipo == "assunto_principal":
        return tabela[(tabela["genero"] == selecao["genero"]) & (tabela["assunto_principal"] == valor)]
    if tipo == "palavra":
        return tabela[(tabela["genero"] == selecao["genero"]) & tabela["titulo"].map(lambda t: valor in palavras(t))]
    if tipo == "ano":
        return tabela[(tabela["ano"] == valor) & (tabela["genero"] == selecao["genero"])]
    if tipo == "pais":
        return tabela[tabela["pais_iso3"] == valor]
    if tipo == "idioma":
        return tabela[tabela["idioma"] == valor]
    if tipo == "assunto":
        return tabela[tabela["assuntos"].map(lambda a: valor in separar(a))]
    if tipo == "livro":
        return tabela[tabela["id"] == valor]
    return tabela


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
            html.P("Gênero → assunto principal; clique em um retângulo para abrir o nível de baixo."),
            dcc.Graph(id="treemap", config=SEM_BARRA),
            html.Div(style=lado_a_lado, children=[
                dcc.Graph(id="pizza", config=SEM_BARRA, style={"flex": "1 1 420px", "minWidth": 0}),
                html.Div(style={"flex": f"0 0 {graficos.LARGURA_NUVEM}px"}, children=[
                    html.H4(id="titulo-nuvem"),
                    dcc.Graph(id="nuvem", config=SEM_BARRA),
                ]),
            ]),
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
            html.P("Cada círculo é um assunto (tamanho = nº de livros, cor = gênero, como na pizza); uma linha liga "
                   "dois assuntos que aparecem no mesmo livro. Só entram assuntos de 2 ou mais livros."),
            dcc.Graph(id="rede"),
        ]),
        dcc.Tab(label="Uso", children=[
            html.H3("Quais livros são mais procurados?"),
            html.P("Cada ponto é um livro; o tamanho é o número de exemplares no ICMC. Livros no alto com pontos "
                   "pequenos são muito procurados e têm poucas cópias."),
            dcc.Graph(id="dispersao"),
        ]),
        dcc.Tab(label="Exploração", children=[
            html.H3("Exploração geral"),
            html.P("Cada linha é um livro (cor = gênero). Arraste sobre um eixo para filtrar; clique na faixa para desfazer."),
            dcc.Graph(id="paralelas"),
        ]),
    ]),

    dcc.Store(id="selecao"),
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


@app.callback(
    Output("histograma", "figure"), Output("treemap", "figure"), Output("pizza", "figure"),
    Output("globo", "figure"), Output("idiomas", "figure"), Output("rede", "figure"),
    Output("dispersao", "figure"), Output("paralelas", "figure"),
    Input("anos", "value"),
)
def atualizar_graficos(anos):
    """Redesenha os gráficos só com os livros publicados nos anos escolhidos."""
    escolhidos = filtrar_anos(livros, anos)
    return (graficos.histograma_anos(livros, anos), graficos.treemap(escolhidos), graficos.pizza(escolhidos),
            graficos.globo(escolhidos), graficos.idiomas(escolhidos), graficos.rede_assuntos(escolhidos),
            graficos.dispersao_uso(escolhidos), graficos.coordenadas_paralelas(escolhidos))


@app.callback(Output("titulo-nuvem", "children"), Output("nuvem", "figure"),
              Input("pizza", "clickData"), Input("anos", "value"))
def mostrar_nuvem(clique, anos):
    """Clique em uma fatia: nuvem de palavras dos títulos daquele gênero (nos anos escolhidos)."""
    if clique is None:
        return "Clique em uma fatia da pizza", graficos.nuvem([])
    genero = clique["points"][0]["label"]
    escolhidos = filtrar_anos(livros, anos)
    return f"Palavras nos títulos: {genero}", graficos.nuvem(escolhidos.loc[escolhidos["genero"] == genero, "titulo"])


@app.callback(
    Output("selecao", "data"),
    Input("treemap", "clickData"), Input("pizza", "clickData"), Input("nuvem", "clickData"),
    Input("histograma", "clickData"), Input("globo", "clickData"), Input("idiomas", "clickData"),
    Input("rede", "clickData"), Input("dispersao", "clickData"), Input("limpar", "n_clicks"),
    prevent_initial_call=True,
)
def selecionar(treemap, pizza, nuvem, histograma, globo, idiomas, rede, dispersao, _):
    """Guarda o último clique, em qualquer gráfico, como {"tipo", "valor", "texto"}. A tabela usa isso."""
    origem = ctx.triggered_id
    if origem == "limpar":
        return None
    if not ctx.triggered[0]["value"]:
        return no_update
    if origem == "treemap":
        ponto = treemap["points"][0]
        pai = ponto.get("parent", "")
        if pai == "":  # clicou em "Todos os livros"
            return None
        if pai == "Todos os livros":  # clicou em um gênero
            return {"tipo": "genero", "valor": ponto["label"], "texto": f"Gênero: {ponto['label']}"}
        genero = pai.split("/")[-1]  # clicou em um assunto dentro de um gênero
        return {"tipo": "assunto_principal", "valor": ponto["label"], "genero": genero,
                "texto": f"{genero} › {ponto['label']}"}
    if origem == "pizza":
        genero = pizza["points"][0]["label"]
        return {"tipo": "genero", "valor": genero, "texto": f"Gênero: {genero}"}
    if origem == "nuvem":
        palavra, genero = nuvem["points"][0]["customdata"][0], pizza["points"][0]["label"]
        return {"tipo": "palavra", "valor": palavra, "genero": genero, "texto": f'{genero} › palavra "{palavra}"'}
    if origem == "histograma":
        ponto = histograma["points"][0]
        return {"tipo": "ano", "valor": ponto["x"], "genero": ponto["customdata"],
                "texto": f"{ponto['customdata']} publicados em {ponto['x']}"}
    if origem == "globo":
        ponto = globo["points"][0]
        return {"tipo": "pais", "valor": ponto["location"], "texto": f"País: {ponto['text']}"}
    if origem == "idiomas":
        idioma = idiomas["points"][0]["y"]
        return {"tipo": "idioma", "valor": idioma, "texto": f"Idioma: {idioma}"}
    if origem == "rede":
        assunto = rede["points"][0]["customdata"][0]
        return {"tipo": "assunto", "valor": assunto, "texto": f"Assunto: {assunto}"}
    if origem == "dispersao":
        livro_id, titulo = dispersao["points"][0]["customdata"][:2]
        return {"tipo": "livro", "valor": livro_id, "texto": f"Livro: {titulo}"}
    return no_update


@app.callback(Output("titulo-tabela", "children"), Output("tabela", "data"),
              Input("selecao", "data"), Input("anos", "value"))
def mostrar_tabela(selecao, anos):
    """Livros dos anos escolhidos e, se houver, do último clique."""
    escolhidos, texto = filtrar_anos(livros, anos), "Todos os livros"
    if selecao:
        escolhidos, texto = filtrar_selecao(escolhidos, selecao), selecao["texto"]
    tabela = escolhidos[list(COLUNAS_TABELA)].copy()
    tabela["ano"] = tabela["ano"].map(lambda a: "" if pd.isna(a) else int(a))
    return f"{texto}: {len(tabela)} livro(s) de {anos[0]} a {anos[1]}", tabela.to_dict("records")


if __name__ == "__main__":
    app.run(debug=True)
