"""
Uma função para cada gráfico do app. Todas recebem a tabela de livros (já filtrada pelos anos
escolhidos) e devolvem uma figura do plotly.
"""
import itertools
from collections import Counter

import networkx as nx
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud

from dados import CORES, genero, palavras, separar

AZUL = "#2a78d6"
CINZA_CLARO = "#e1e0d9"
TEXTO_SECUNDARIO = "#52514e"


def layout_padrao(fig, altura):
    fig.update_layout(height=altura, font_family="sans-serif", plot_bgcolor="white", paper_bgcolor="white")
    return fig


def vazio(mensagem):
    """Figura sem dados, só com um aviso."""
    fig = go.Figure()
    fig.add_annotation(text=mensagem, showarrow=False, font=dict(color=TEXTO_SECUNDARIO, size=14))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return layout_padrao(fig, 200)


def histograma_anos(livros, anos):
    """Barras empilhadas: livros por ano de publicação e gênero. A faixa de anos escolhida fica destacada.
    Arrastar sobre o gráfico seleciona um intervalo de anos (linking + brushing: dragmode="select")."""
    contagem = livros.dropna(subset=["ano"]).groupby(["ano", "genero"]).size().reset_index(name="livros")
    fig = go.Figure()
    for g, cor in CORES.items():
        d = contagem[contagem["genero"] == g]
        if len(d):
            fig.add_trace(go.Bar(x=d["ano"], y=d["livros"], name=g, marker_color=cor,
                                 hovertemplate=f"<b>%{{y}} livros</b><br>{g} · %{{x}}<extra></extra>"))
    fig.add_vrect(x0=anos[0] - 0.5, x1=anos[1] + 0.5, fillcolor=AZUL, opacity=0.08, line_width=0)
    fig.update_layout(barmode="stack", bargap=0.15, dragmode="select", selectdirection="h",
                      legend=dict(orientation="h", y=1.18), margin=dict(l=50, r=10, t=30, b=40))
    fig.update_xaxes(title="Ano de publicação")
    fig.update_yaxes(title="Livros", gridcolor=CINZA_CLARO)
    return layout_padrao(fig, 260)


def treemap(livros, conjunto=None):
    """Treemap gênero -> assunto principal (no máximo 9 assuntos + "Outros assuntos" por gênero).
    Área de cada retângulo = número de livros. conjunto = retângulo escolhido (None = todos):
    o treemap fica aberto no gênero escolhido e o assunto escolhido ganha borda escura."""
    if livros.empty:
        return vazio("Nenhum livro nos anos escolhidos")
    fig = px.treemap(livros, path=[px.Constant("Todos os livros"), "genero", "assunto_treemap"],
                     color="genero", color_discrete_map={"(?)": CINZA_CLARO, **CORES})
    # Os retângulos têm ids do tipo "Todos os livros/Computação/INTELIGÊNCIA ARTIFICIAL"
    genero_aberto = f"Todos os livros/{conjunto['genero']}" if conjunto else None
    assunto = f"{genero_aberto}/{conjunto['assunto']}" if conjunto and conjunto.get("assunto") else None
    ids = list(fig.data[0].ids)
    if genero_aberto not in ids:  # o gênero escolhido não tem livros nos anos escolhidos
        genero_aberto = None
    fig.update_traces(
        level=genero_aberto,  # retângulo que fica aberto (None = todos os livros)
        marker_line_color=["#0b0b0b" if i == assunto else "white" for i in ids],
        marker_line_width=[4 if i == assunto else 2 for i in ids],
        root_color=CINZA_CLARO, hovertemplate="<b>%{label}</b><br>%{value} livros<extra></extra>",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    return layout_padrao(fig, 480)


# Nuvem de palavras: a biblioteca wordcloud calcula onde cada palavra fica e o tamanho dela;
# desenhamos as palavras com plotly porque assim dá para clicar nelas.
LARGURA_NUVEM, ALTURA_NUVEM = 900, 380


def nuvem(titulos):
    contagem = Counter(p for t in titulos for p in palavras(t))  # nº de livros com a palavra no título
    if not contagem:
        return vazio("Nenhuma palavra")
    layout = WordCloud(width=LARGURA_NUVEM, height=ALTURA_NUVEM, prefer_horizontal=1, max_words=80,
                       max_font_size=64, min_font_size=11, random_state=1).generate_from_frequencies(contagem).layout_
    x, y, textos, tamanhos = [], [], [], []
    alvo_x, alvo_y, alvo_tamanho, alvo_palavra = [], [], [], []
    for (palavra, _), tamanho, (topo, esquerda), _, _ in layout:
        largura = len(palavra) * tamanho * 0.6  # fonte monoespaçada: cada letra tem ~0,6 do tamanho
        textos.append(palavra)
        tamanhos.append(tamanho)
        x.append(esquerda + largura / 2)  # centro da palavra
        y.append(topo + tamanho / 2)
        # Pontos invisíveis a cada 8 px ao longo da palavra: o clique funciona em qualquer parte dela
        for i in range(int(largura // 8) + 1):
            alvo_x.append(esquerda + 4 + 8 * i)
            alvo_y.append(topo + tamanho / 2)
            alvo_tamanho.append(tamanho * 0.6)  # menor que a letra, para não invadir as palavras vizinhas
            alvo_palavra.append(palavra)
    fig = go.Figure()
    fig.add_trace(go.Scatter(  # as palavras (só desenho)
        x=x, y=y, text=textos, mode="text", hoverinfo="skip",
        textfont=dict(size=tamanhos, color="#2b2b28", family="Droid Sans Mono"),  # ver assets/fonte.css
    ))
    fig.add_trace(go.Scatter(  # os pontos invisíveis (recebem o mouse e o clique)
        x=alvo_x, y=alvo_y, mode="markers", marker=dict(size=alvo_tamanho, opacity=0),
        customdata=[[p, contagem[p]] for p in alvo_palavra],
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} livro(s)<extra></extra>",
    ))
    fig.update_xaxes(visible=False, range=[0, LARGURA_NUVEM])
    fig.update_yaxes(visible=False, range=[ALTURA_NUVEM, 0])
    fig.update_layout(width=LARGURA_NUVEM, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, hoverdistance=5)
    return layout_padrao(fig, ALTURA_NUVEM)


def globo(livros):
    """Globo (projeção ortográfica, arrastar gira). Cor = nº de livros publicados no país, em escala
    logarítmica porque o Brasil tem muito mais livros que os outros países."""
    por_pais = livros[livros["pais_iso3"] != ""].groupby(["pais_iso3", "pais"]).size().reset_index(name="livros")
    if por_pais.empty:
        return vazio("Nenhum livro nos anos escolhidos")
    fig = go.Figure(go.Choropleth(
        locations=por_pais["pais_iso3"], z=np.log10(por_pais["livros"]),
        text=por_pais["pais"], customdata=por_pais["livros"],
        colorscale=["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"],  # um só tom de azul: bom para daltônicos
        zmin=0, zmax=max(1, np.log10(por_pais["livros"].max())), marker_line_color="white",
        hovertemplate="<b>%{text}</b><br>%{customdata} livros<extra></extra>",
        colorbar=dict(title="Livros", tickvals=[0, 1, 2, 3, 4], ticktext=["1", "10", "100", "1.000", "10.000"]),
    ))
    fig.update_geos(projection_type="orthographic", projection_rotation=dict(lon=-50, lat=-10),
                    showframe=True, framecolor="#c3c2b7", showocean=True, oceancolor="#f7f7f5",
                    showcoastlines=False, showcountries=True, countrycolor="white", showland=True, landcolor=CINZA_CLARO)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    return layout_padrao(fig, 520)


def idiomas(livros):
    """Barras horizontais: livros por idioma."""
    contagem = livros["idioma"].value_counts().sort_values()
    fig = go.Figure(go.Bar(
        x=contagem.values, y=contagem.index, orientation="h", marker=dict(color=AZUL, cornerradius=4),
        text=contagem.values, textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{x} livros</b><br>%{y}<extra></extra>",
    ))
    fig.update_xaxes(visible=False)
    fig.update_layout(margin=dict(l=10, r=40, t=10, b=10), bargap=0.35)
    return layout_padrao(fig, 60 + 32 * len(contagem))


def rede_assuntos(livros, max_assuntos=50):
    """Rede de assuntos: cada nó é um assunto (tamanho = nº de livros, cor = gênero) e cada aresta liga
    dois assuntos que aparecem juntos em algum livro. Posições calculadas por forças (molas que atraem
    assuntos ligados + repulsão entre todos), o algoritmo force-directed da Aula06."""
    listas = livros["assuntos"].map(lambda a: set(separar(a)))
    contagem = Counter(a for lista in listas for a in lista)
    principais = {a for a, n in contagem.most_common(max_assuntos) if n >= 2}
    rede = nx.Graph()
    for lista in listas:
        for a, b in itertools.combinations(sorted(lista & principais), 2):
            peso = rede.get_edge_data(a, b, {"peso": 0})["peso"]
            rede.add_edge(a, b, peso=peso + 1)
    if rede.number_of_nodes() == 0:
        return vazio("Poucos livros para formar a rede")
    pos = nx.spring_layout(rede, weight="peso", seed=1)

    linhas_x, linhas_y = [], []
    for a, b in rede.edges():
        linhas_x += [pos[a][0], pos[b][0], None]  # None separa uma aresta da outra
        linhas_y += [pos[a][1], pos[b][1], None]
    nos = list(rede.nodes())
    maiores = set(sorted(nos, key=lambda a: -contagem[a])[:12])  # só os 12 maiores ganham rótulo fixo
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=linhas_x, y=linhas_y, mode="lines", line=dict(width=1, color="#c3c2b7"),
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=[pos[a][0] for a in nos], y=[pos[a][1] for a in nos], mode="markers+text",
        text=[a.title() if a in maiores else "" for a in nos], textposition="top center",
        textfont=dict(size=11, color=TEXTO_SECUNDARIO),
        marker=dict(size=[10 + 6 * np.sqrt(contagem[a]) for a in nos], color=[CORES[genero(a)] for a in nos],
                    line=dict(color="white", width=1.5)),
        customdata=[[a, contagem[a], rede.degree(a)] for a in nos],
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} livros · ligado a %{customdata[2]} assuntos<extra></extra>",
    ))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
    return layout_padrao(fig, 560)


def dispersao_uso(livros):
    """Dispersão: ano de publicação × empréstimos; tamanho do ponto = nº de exemplares no ICMC."""
    fig = go.Figure()
    for g, cor in CORES.items():
        d = livros[livros["genero"] == g].dropna(subset=["ano"])
        if len(d):
            fig.add_trace(go.Scatter(
                x=d["ano"], y=d["emprestimos"], mode="markers", name=g,
                marker=dict(color=cor, size=6 + 3 * d["exemplares"].clip(upper=10), opacity=0.85,
                            line=dict(color="white", width=1)),
                customdata=d[["id", "titulo", "exemplares"]].values,
                hovertemplate="<b>%{customdata[1]}</b><br>%{x} · %{y} empréstimos · %{customdata[2]} exemplar(es)<extra></extra>",
            ))
    fig.update_xaxes(title="Ano de publicação", gridcolor=CINZA_CLARO)
    fig.update_yaxes(title="Empréstimos (campo a confirmar com a biblioteca)", gridcolor=CINZA_CLARO)
    fig.update_layout(legend=dict(orientation="h", y=1.1), margin=dict(l=60, r=10, t=40, b=50))
    return layout_padrao(fig, 520)
