# Trabalho de Grafos (COS 242)

Biblioteca de grafos em Python, com um motor opcional em C, e os programas usados
nos estudos de caso das três partes do trabalho.

- **Parte 1:** grafos sem pesos, BFS, DFS, distâncias, diâmetro, componentes.
- **Parte 2:** pesos, Dijkstra com vetor e com heap, representação CSR e motor C.
- **Parte 3:** grafos direcionados, Bellman-Ford, Floyd-Warshall e Johnson.
  Detalhes e resultados em [PARTE3.md](PARTE3.md).

## Módulos

| Arquivo | Conteúdo |
|---|---|
| `grafo.py` | classe `Grafo`: lista ou matriz de adjacência, com ou sem pesos, direcionado ou não |
| `grafo_csr.py` | `GrafoCSR`: vetores de adjacência compactos (NumPy) para grafos grandes |
| `entrada_saida.py` | leitura do arquivo (`.txt` ou `.txt.gz`, duas ou três colunas) |
| `estatisticas.py` | nº de arestas, grau mínimo, máximo, médio e mediana |
| `busca.py`, `dfs.py` | BFS e DFS (pai e nível) e componentes conexas |
| `distancias.py` | distância sem pesos, diâmetro exato e aproximado |
| `prioridades.py` | filas de prioridade (vetor e heap indexado) para Dijkstra |
| `caminhos_minimos.py` | Dijkstra e reconstrução de caminhos |
| `caminhos_p3.py` | Bellman-Ford, Floyd-Warshall (clássico e blocado), Johnson |
| `motor_c.py`, `c/` | motor C: leitura, Dijkstra, Bellman-Ford, Floyd-Warshall e Johnson |
| `main.py` | menu interativo |

Scripts dos estudos de caso:

| Arquivo | Uso |
|---|---|
| `experimentos.py`, `tabela.py`, `memoria.py` | parte 1 |
| `experimentos_p2.py`, `perfil_p2.py`, `colaboracao.py` | parte 2 |
| `comparacao_todos_pares.py` | parte 3, todas as versões em Python e C (caminho principal) |
| `experimentos_p3.py`, `benchmark_p3.py`, `calibracao_p3.py`, `distancias_amostrais_p3.py` | parte 3, caminho só Python para pouca memória |

## Formato de entrada

Primeira linha: número de vértices. Demais linhas: uma aresta por linha, com os
dois vértices e, opcionalmente, o peso.

```
5
1 2 0.5
2 5 -1.2
5 3 3
```

Em grafos direcionados, cada linha é um arco do primeiro para o segundo vértice.

## Instalação

```sh
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
make testes
```

`make` compila `c/libgrafos.so` (GCC, zlib e OpenMP). Sem o motor C, a
biblioteca funciona só em Python e os testes do motor são pulados
(`python -m unittest discover`).

## Uso interativo

```sh
python main.py                 # não direcionado
python main.py --direcionado   # cada linha vira um arco
```

O programa pergunta o arquivo e a representação (lista, matriz ou CSR), e o
menu oferece:

| Opção | Algoritmo |
|---|---|
| 1, 2 | BFS e DFS, com a árvore gravada em `arvore_<busca>_<raiz>.txt` |
| 3, 4, 5, 6 | distância, diâmetro, componentes e estatísticas |
| 7 | Dijkstra (vetor ou heap, Python ou C) |
| 8 | Bellman-Ford até um destino, com os dois indicadores de ciclo negativo |
| 9 | Floyd-Warshall: Python clássico ou blocado, C clássico ou blocado |
| 10 | Johnson (Python ou C) |

As opções em C aparecem quando o grafo está em CSR e o motor foi compilado.

## Uso como biblioteca

```python
from entrada_saida import ler_grafo
from busca import BFS
from caminhos_minimos import dijkstra
from caminhos_p3 import bellman_ford, floyd_warshall, johnson

grafo = ler_grafo("grafo_W_2.txt.gz", "csr", direcionado=True)

pai, nivel = BFS(grafo, 1)
distancias, pais = dijkstra(grafo, 1, "heap")

bf = bellman_ford(grafo, 100, verificar_grafo=True)
bf.distancias[10], bf.caminho(10), bf.tem_ciclo_negativo, bf.ciclo_no_grafo

fw = floyd_warshall(grafo)
fw.distancia(10, 20), fw.caminho(10, 20), fw.submatriz([10, 20, 30])
```

Com o motor C:

```python
import motor_c

motor_c.bellman_ford_c(grafo, 100)
motor_c.floyd_warshall_c(grafo, "blocado")
motor_c.bellman_ford_todos_pares_c(grafo)
motor_c.johnson_c(grafo)
```

Os resultados de todos os pares expõem `distancia`, `caminho`, `submatriz` e
`tem_ciclo_negativo`. `inf` indica destino inalcançável, e `-inf` indica que o
caminho pode passar por um ciclo negativo.

## Estudos de caso

```sh
python experimentos.py grafo_1.txt.gz          # parte 1
python tabela.py
python experimentos_p2.py grafo_W_3.txt.gz     # parte 2
python comparacao_todos_pares.py grafo_W_1.txt.gz grafo_W_2.txt.gz   # parte 3
```

As medições de tempo cobrem só os algoritmos: leitura do arquivo, montagem das
estruturas e escrita dos resultados ficam fora do cronômetro. A parte 3 está
detalhada no [guia de experimentos](GUIA_EXPERIMENTOS_P3.md). Os grafos de
estudo de caso não estão no repositório; baixe-os no site da disciplina.
