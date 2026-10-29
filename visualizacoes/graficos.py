"""
Uma função para cada gráfico do app. Todas recebem a tabela de livros e devolvem uma figura do plotly.
"""
from collections import Counter

import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud

from dados import CORES, palavras

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


def treemap(livros, conjunto=None):
    """Treemap gênero -> assunto principal (no máximo 9 assuntos + "Outros assuntos" por gênero).
    Área de cada retângulo = número de livros. conjunto = retângulo escolhido (None = todos):
    o treemap fica aberto no gênero escolhido e o assunto escolhido ganha borda escura."""
    if livros.empty:
        return vazio("Nenhum livro")
    fig = px.treemap(livros, path=[px.Constant("Todos os livros"), "genero", "assunto_treemap"],
                     color="genero", color_discrete_map={"(?)": CINZA_CLARO, **CORES})
    # Os retângulos têm ids do tipo "Todos os livros/Computação/INTELIGÊNCIA ARTIFICIAL"
    genero = f"Todos os livros/{conjunto['genero']}" if conjunto else None
    assunto = f"{genero}/{conjunto['assunto']}" if conjunto and conjunto.get("assunto") else None
    ids = list(fig.data[0].ids)
    fig.update_traces(
        level=genero,  # retângulo que fica aberto (None = todos os livros)
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
