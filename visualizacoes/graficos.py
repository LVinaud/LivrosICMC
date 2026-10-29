"""
Uma função para cada gráfico do app. Todas recebem a tabela de livros e devolvem uma figura do plotly.
"""
import numpy as np
import plotly.graph_objects as go

from dados import CORES

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


def clarear(cor, fracao):
    """Mistura a cor com branco: fracao 0 = a própria cor, 1 = branco."""
    r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02x}{:02x}{:02x}".format(*(round(c + (255 - c) * fracao) for c in (r, g, b)))


def rosa_emprestimos(livros, n=5):
    """Rosa (polar area / coxcomb): cada fatia é um gênero; dentro dela, os n livros mais emprestados,
    do centro para fora (tom mais escuro = mais emprestado). A ÁREA de cada pedaço é proporcional ao
    número de empréstimos (o raio cresce com a raiz quadrada), para não exagerar os valores grandes."""
    generos = [g for g in CORES if g in set(livros["genero"])]
    mais_emprestados = {g: livros[livros["genero"] == g].nlargest(n, "emprestimos") for g in generos}
    fig = go.Figure()
    for posicao in range(n):  # uma camada para o 1º mais emprestado de cada gênero, outra para o 2º, ...
        theta, base, comprimento, cores, hover = [], [], [], [], []
        for g in generos:
            top = mais_emprestados[g]
            if posicao >= len(top):
                continue
            livro = top.iloc[posicao]
            antes = top["emprestimos"].iloc[:posicao].sum()  # empréstimos dos livros mais perto do centro
            theta.append(g)
            base.append(np.sqrt(antes))
            comprimento.append(np.sqrt(antes + livro["emprestimos"]) - np.sqrt(antes))
            cores.append(clarear(CORES[g], 0.15 * posicao))
            hover.append([livro["id"], livro["titulo"], livro["emprestimos"], posicao + 1])
        fig.add_trace(go.Barpolar(
            theta=theta, base=base, r=comprimento, marker_color=cores,
            marker_line_color="white", marker_line_width=1.5, customdata=hover,
            hovertemplate="<b>%{customdata[1]}</b><br>%{theta} · %{customdata[3]}º mais emprestado"
                          "<br>%{customdata[2]} empréstimos<extra></extra>",
        ))
    total_maximo = max(top["emprestimos"].sum() for top in mais_emprestados.values())
    marcas = [m for m in [50, 100, 250, 500, 1000, 2000] if m <= total_maximo]
    fig.update_layout(
        showlegend=False, margin=dict(l=60, r=60, t=40, b=40),
        polar=dict(
            bgcolor="white", bargap=0.06,
            angularaxis=dict(direction="clockwise", rotation=90, tickfont=dict(size=13), linecolor=CINZA_CLARO),
            # A escala fica na divisa entre a primeira e a última fatia, para não cobrir os pedaços
            radialaxis=dict(tickvals=np.sqrt(marcas), ticktext=marcas, angle=90 + 180 / len(generos), tickangle=90,
                            tickfont=dict(size=10, color=TEXTO_SECUNDARIO), gridcolor=CINZA_CLARO,
                            linecolor=CINZA_CLARO),
        ),
    )
    return layout_padrao(fig, 600)


def globo(livros):
    """Globo (projeção ortográfica, arrastar gira). Cor = nº de livros publicados no país, em escala
    logarítmica porque o Brasil tem muito mais livros que os outros países."""
    por_pais = livros[livros["pais_iso3"] != ""].groupby(["pais_iso3", "pais"]).size().reset_index(name="livros")
    if por_pais.empty:
        return vazio("Nenhum livro")
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
    return layout_padrao(fig, 560)


def linha_do_tempo(livros):
    """Barras empilhadas: livros publicados por ano e gênero."""
    contagem = livros.dropna(subset=["ano"]).groupby(["ano", "genero"]).size().reset_index(name="livros")
    fig = go.Figure()
    for g, cor in CORES.items():
        d = contagem[contagem["genero"] == g]
        if len(d):
            fig.add_trace(go.Bar(x=d["ano"], y=d["livros"], name=g, marker_color=cor,
                                 customdata=[g] * len(d),  # para saber o gênero da barra clicada
                                 hovertemplate=f"<b>%{{y}} livros</b><br>{g} · %{{x}}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.15, legend=dict(orientation="h", y=1.12),
                      margin=dict(l=50, r=10, t=30, b=40))
    fig.update_xaxes(title="Ano de publicação")
    fig.update_yaxes(title="Livros", gridcolor=CINZA_CLARO)
    return layout_padrao(fig, 460)
