# Trabalho de Grafos - Parte 1 (COS 242)

Biblioteca para manipulação de grafos não-direcionados e os programas
usados nos estudos de caso.

## Módulos

| Arquivo | Conteúdo |
|---|---|
| `grafo.py` | classe `Grafo`: lista ou matriz de adjacência (só a escolhida é alocada) |
| `entrada_saida.py` | leitura do arquivo do grafo (aceita `.txt` e `.txt.gz`) |
| `estatisticas.py` | nº de arestas, grau mínimo, máximo, médio e mediana |
| `busca.py` | BFS (pai e nível) e componentes conexas |
| `dfs.py` | DFS iterativa (pai e nível) e componentes por DFS |
| `distancias.py` | distância entre dois vértices, diâmetro exato e aproximado |
| `saida.py` | gravação da árvore de busca em arquivo |
| `memoria.py` | medição da memória usada por cada representação |
| `experimentos.py` | roda os 7 estudos de caso e grava `resultados_<grafo>.txt` |
| `tabela.py` | junta os resultados em tabelas (`tabelas.md`) |

## Formato de entrada

Primeira linha: número de vértices. Demais linhas: uma aresta por linha,
com os dois vértices separados por espaço.

```
5
1 2
2 5
5 3
4 5
1 5
```

## Uso interativo

```bash
python3 main.py
```

Pergunta o arquivo do grafo e a representação (lista ou matriz), mostra
as estatísticas e abre um menu com BFS, DFS, distância entre dois
vértices, diâmetro e componentes conexas. As árvores de BFS/DFS são
gravadas em `arvore_<busca>_<raiz>.txt`, uma linha por vértice no
formato `vertice pai nivel` (a raiz tem pai 0 e nível 0).

## Uso como biblioteca

```python
from entrada_saida import ler_grafo
from busca import BFS, componentes
from dfs import DFS
from distancias import distancia, diametro, diametro_aproximado

grafo = ler_grafo("grafo_1.txt.gz", "lista")   # ou "matriz"

pai, nivel = BFS(grafo, 1)
pai, nivel = DFS(grafo, 1)

distancia(grafo, 10, 20)        # -1 (INFINITO) se não houver caminho
diametro(grafo)                 # exato: uma BFS por vértice
diametro_aproximado(grafo)      # varredura dupla por componente
componentes(grafo)              # (quantidade, tamanhos, listas de vértices)
```

## Estudos de caso

```bash
python3 experimentos.py grafo_1.txt.gz              # todos os experimentos
python3 experimentos.py grafo_3.txt.gz --sem-matriz # pula a matriz
python3 tabela.py                                   # consolida em tabelas.md
```

Opções úteis do `experimentos.py`:

- `--buscas N` / `--buscas-matriz N`: número de buscas usadas na média de tempo
- `--sem-matriz`: pula os experimentos com matriz de adjacência
- `--sem-diametro-exato` / `--forcar-diametro-exato`

O programa pula sozinho o que for inviável no grafo dado: a matriz de
adjacência ocupa n² bytes (131 GB para n = 375.000) e o diâmetro exato
custa uma BFS por vértice. Nos dois casos o motivo e a estimativa ficam
registrados no arquivo de resultados.

As medições de tempo cobrem apenas o algoritmo de busca: leitura do
arquivo e escrita dos resultados ficam fora do cronômetro.
