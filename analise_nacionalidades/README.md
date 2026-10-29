# País dos autores

Abra `nacionalidade_autores.ipynb` e execute as células em ordem.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r analise_nacionalidades/requirements.txt
python -m jupyter lab analise_nacionalidades/nacionalidade_autores.ipynb
```

No VS Code, selecione o kernel desse ambiente. Use `LIMITE = 5` para testar
e `LIMITE = None` para processar todos e salvar `dados/livros_autores.csv`.

Fluxo: ISBN (ou busca por título + autor) → primeiro autor nas APIs de livros
→ identificador de autor → cidadania/nacionalidade → país de nascimento.
Open Library e BrasilAPI são as fontes bibliográficas principais; Google Books
é opcional com `GOOGLE_BOOKS_API_KEY` no ambiente. Biografia: Wikidata e DBpedia.

O notebook gera somente um CSV, não usa cache e não altera o catálogo original.
Cada execução consulta as APIs de novo. Fonte, critério e situação ficam nas
colunas do resultado. ISBN obtido por título pode ser de outra edição;
nascimento é uma aproximação, não cidadania. Lacunas permanecem explícitas.

As consultas processam até quatro livros em paralelo (`TRABALHADORES = 4`).
Use `1` para comparar com a execução sequencial. Cada trabalhador reutiliza
suas conexões, e a espera entre consultas é controlada por API: cerca de uma
consulta/s na Open Library e até duas/s nas outras fontes. Se houver erro 429,
respeitamos `Retry-After` (ou esperamos 60 s quando ele não vier) e tentamos
novamente uma vez. Os limites são compartilhados entre os trabalhadores.

O progresso aparece conforme os livros terminam; o CSV mantém a ordem original.
O tempo total é exibido ao final. O ganho depende da latência e dos limites das APIs.
Não é preciso instalar dependências novas. Depois de atualizar o notebook,
interrompa qualquer execução antiga, reinicie o kernel e execute as células em ordem.

Referência: [limites da Open Library](https://openlibrary.org/developers/api#rate-limits).

O CSV de autores representa a última execução da análise. Depois de atualizar
o catálogo em `dados/livros_icmc.csv`, execute o notebook novamente para
atualizar `dados/livros_autores.csv`; os resultados não são acrescentados automaticamente.
