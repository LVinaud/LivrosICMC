// O Plotly dá zoom sozinho quando se clica num retângulo do treemap (inclusive num assunto, que
// acabaria ocupando o gráfico inteiro). Aqui desligamos esse zoom automático: quem decide o que fica
// aberto é o app (propriedade "level" em graficos.treemap).
// O Dash carrega sozinho os arquivos da pasta assets.
const esperarTreemap = setInterval(function () {
  const grafico = document.querySelector("#treemap .js-plotly-plot");
  if (grafico && grafico.on) {
    grafico.on("plotly_treemapclick", function (evento) {
      grafico.emit("plotly_click", evento);  // avisa o Dash do clique (vira o clickData do gráfico)
      return false;                          // e impede o zoom automático do Plotly
    });
    clearInterval(esperarTreemap);
  }
}, 300);
