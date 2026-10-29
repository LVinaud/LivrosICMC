"""
Visualizações dos livros da Biblioteca do ICMC (entrega 1).

- Empréstimos: rosa com os 5 livros mais emprestados de cada gênero.
- Origem: mapa com o número de livros por país de publicação.
- Linha do tempo: livros publicados por ano e gênero.
Clicar num gráfico mostra os livros correspondentes na tabela no fim da página.

Lê dados/livros_tratados.csv (gerado por processamento/tratar_dados.py).
Uso: python app.py   e abrir http://127.0.0.1:8050
"""
import os

import numpy as np
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, ctx, dash_table, dcc, html

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados")
livros = pd.read_csv(os.path.join(PASTA, "livros_tratados.csv"))

# Uma cor por gênero, a mesma em todos os gráficos. Nesta ordem, cores vizinhas continuam
# distinguíveis por quem tem daltonismo (verificado com um simulador de daltonismo).
CORES = {"Computação": "#2a78d6", "Matemática": "#eb6834", "Educação": "#1baf7a", "Literatura": "#eda100",
         "História e biografias": "#e87ba4", "Estatística": "#008300", "Outros": "#a3a29c"}

# 1. Barras horizontais: os 5 livros mais emprestados de cada gênero, um painel por gênero
top5 = livros.sort_values("emprestimos", ascending=False).groupby("genero").head(5).copy()
# Rótulo do eixo: posição + título curto (a posição evita juntar dois livros com o mesmo título)
top5["rotulo"] = (top5.groupby("genero").cumcount() + 1).astype(str) + "º " + top5["titulo"].str.slice(0, 45)
# Gêneros do que tem mais empréstimos para o que tem menos
ordem_generos = livros.groupby("genero")["emprestimos"].sum().sort_values(ascending=False).index.tolist()
barras = px.bar(top5, x="emprestimos", y="rotulo", color="genero", facet_row="genero", orientation="h",
                text="emprestimos", custom_data=["id", "titulo"], color_discrete_map=CORES,
                category_orders={"genero": ordem_generos}, labels={"emprestimos": "Empréstimos", "rotulo": ""})
barras.update_traces(textposition="outside", hovertemplate="<b>%{customdata[1]}</b><br>%{x} empréstimos<extra></extra>")
# Cada painel mostra só os seus livros, do 1º (em cima) ao 5º; a escala de x é a mesma em todos
barras.update_yaxes(matches=None, categoryorder="category descending")
barras.for_each_annotation(lambda a: a.update(text=a.text.replace("genero=", "")))  # "genero=Matemática" -> "Matemática"
barras.update_layout(height=1100, showlegend=False)

# 2. Mapa: livros por país de publicação. A cor usa escala logarítmica (1, 10, 100...) porque o Brasil
#    tem muito mais livros que os outros países; numa escala comum todos os outros ficariam iguais.
por_pais = livros.groupby(["pais_iso3", "pais"]).size().reset_index(name="livros")
mapa = px.choropleth(por_pais, locations="pais_iso3", color=np.log10(por_pais["livros"]), hover_name="pais",
                     custom_data=["livros"], projection="natural earth",
                     color_continuous_scale=["#86b6ef", "#0d366b"])  # um só tom de azul, bom para daltônicos
mapa.update_traces(hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]} livros<extra></extra>")
mapa.update_coloraxes(colorbar=dict(title="Livros", tickvals=[0, 1, 2, 3], ticktext=["1", "10", "100", "1000"]))
mapa.update_layout(height=520, margin=dict(l=0, r=0, t=0, b=0))

# 3. Linha do tempo: livros publicados por ano, uma linha por gênero
anos = range(livros["ano"].min(), livros["ano"].max() + 1)
# Tabela ano x gênero com 0 nos anos sem livro (senão a linha ligaria direto os anos com livros)
por_ano = (livros.groupby(["ano", "genero"]).size().unstack(fill_value=0).reindex(anos, fill_value=0)
           .stack().reset_index(name="livros"))
linha = px.line(por_ano, x="ano", y="livros", color="genero", markers=True, custom_data=["genero"],
                color_discrete_map=CORES, category_orders={"genero": list(CORES)},
                labels={"ano": "Ano de publicação", "livros": "Livros", "genero": "Gênero"})
linha.update_layout(height=460, hovermode="x unified")  # o mouse num ano mostra todos os gêneros

COLUNAS = {"titulo": "Título", "autores": "Autores", "ano": "Ano", "genero": "Gênero", "pais": "País",
           "idioma": "Idioma", "exemplares": "Exemplares", "emprestimos": "Empréstimos"}

app = Dash(__name__, title="Livros do ICMC")
app.layout = html.Div(style={"fontFamily": "sans-serif", "maxWidth": "1200px", "margin": "auto"}, children=[
    html.H1("Livros da Biblioteca do ICMC"),
    html.P(f"{len(livros)} livros. Clique nos gráficos para ver os livros na tabela no fim da página."),
    dcc.Tabs([
        dcc.Tab(label="Empréstimos", children=[
            html.H3("Quais livros são mais emprestados em cada gênero?"),
            html.P("Os 5 livros mais emprestados de cada gênero. Os gêneros vão do que tem mais empréstimos para o que "
                   "tem menos, e todos usam a mesma escala. Clique numa barra para ver o livro."),
            dcc.Graph(id="barras", figure=barras),
        ]),
        dcc.Tab(label="Origem", children=[
            html.H3("De onde vêm os livros do acervo?"),
            html.P("Número de livros por país de publicação."),
            dcc.Graph(id="mapa", figure=mapa),
        ]),
        dcc.Tab(label="Linha do tempo", children=[
            html.H3("Quantos livros de cada gênero foram publicados por ano?"),
            html.P("Clique num ponto para ver os livros daquele gênero e ano; clique num gênero da legenda para "
                   "escondê-lo ou mostrá-lo."),
            dcc.Graph(id="linha", figure=linha),
        ]),
    ]),
    html.H3(id="titulo-tabela"),
    html.Button("Mostrar todos os livros", id="limpar"),
    dash_table.DataTable(id="tabela", columns=[{"id": c, "name": n} for c, n in COLUNAS.items()],
                         page_size=15, sort_action="native", filter_action="native",
                         style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto"}),
])


@app.callback(Output("titulo-tabela", "children"), Output("tabela", "data"),
              Input("barras", "clickData"), Input("mapa", "clickData"), Input("linha", "clickData"),
              Input("limpar", "n_clicks"))
def mostrar_livros(clique_barras, clique_mapa, clique_linha, _):
    """Mostra na tabela os livros do último gráfico clicado."""
    escolhidos, texto = livros, "Todos os livros"
    if ctx.triggered_id == "barras":
        id_livro, titulo = clique_barras["points"][0]["customdata"]
        escolhidos, texto = livros[livros["id"] == id_livro], titulo
    elif ctx.triggered_id == "mapa":
        ponto = clique_mapa["points"][0]
        escolhidos, texto = livros[livros["pais_iso3"] == ponto["location"]], f"Publicados em: {ponto['hovertext']}"
    elif ctx.triggered_id == "linha":
        ponto = clique_linha["points"][0]
        genero, ano = ponto["customdata"][0], ponto["x"]
        escolhidos, texto = livros[(livros["genero"] == genero) & (livros["ano"] == ano)], f"{genero} em {ano}"
    escolhidos = escolhidos.sort_values("emprestimos", ascending=False)
    return f"{texto} ({len(escolhidos)} livro(s))", escolhidos[list(COLUNAS)].to_dict("records")


if __name__ == "__main__":
    app.run(debug=True)
