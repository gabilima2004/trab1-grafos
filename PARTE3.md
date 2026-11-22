# COS242 | Parte 3 ? Caminhos mínimos

Código-fonte da biblioteca em [trab1-grafos](https://github.com/gabilima2004/trab1-grafos).
A implementação da Parte 3 está na branch local `trabalho-p3`.

## Representação e algoritmos

`ler_grafo(arquivo, representacao="csr", direcionado=True)` interpreta cada linha
como um arco do primeiro vértice para o segundo. Lista, matriz e CSR armazenam
apenas a saída quando o grafo é direcionado. O padrão é não direcionado.
BFS, DFS e Dijkstra já percorriam vizinhos de saída. Dijkstra rejeita arestas de
peso negativo. A opção `python main.py --direcionado` habilita essa leitura no menu.

Bellman-Ford começa no destino e percorre o grafo transposto. O vetor de sucessores
reconstrói rotas no sentido original. As otimizações adotadas foram parada quando
uma rodada não melhora distâncias e relaxamento a partir dos vértices atualizados na
rodada anterior. O enunciado remete à aula sem especificar as duas otimizações.
Uma melhoria na rodada de número `n` detecta ciclo negativo capaz de alcançar o
destino. Em grafos com pesos negativos, a implementação também verifica
periodicamente se os sucessores já contêm um ciclo de peso estritamente negativo.
A detecção propaga `-inf` aos vértices que podem passar pelo ciclo e chegar ao destino.

Floyd-Warshall atualiza em lugar uma matriz de distâncias e outra de
predecessores. A linha `u` dos predecessores descreve os caminhos mínimos com
origem em `u`, usando 0 onde não há predecessor. Os temporários ocupam memória
linear. Um valor negativo na diagonal indica ciclo negativo. Pares para os
quais um caminho pode passar por esse ciclo recebem `-inf`. Nos dois algoritmos,
`inf` indica que o destino é inalcançável e `caminho(...)` devolve lista vazia
quando a distância é infinita em qualquer sentido.

## Reprodução

O [guia de experimentos](GUIA_EXPERIMENTOS_P3.md) descreve o cronômetro retomável e as tabelas seletivas obtidas por Bellman-Ford para os cinco grafos oficiais. A amostra calculada por Bellman-Ford está em `resultados_p3/amostrais/`.

Instale as dependências já usadas na Parte 2. No Linux, `make testes` compila o
motor C e roda os testes das Partes 2 e 3. `unittest discover` pula os testes
do motor C se ele estiver ausente. Foram aprovados 22 testes, incluindo os do
motor C com uma adaptação temporária de compilação para MinGW no Windows.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -v
python experimentos_p3.py /caminho/grafo_W_1.txt.gz /caminho/grafo_W_2.txt.gz /caminho/grafo_W_3.txt.gz /caminho/grafo_W_4.txt.gz /caminho/grafo_W_5.txt.gz
```

O script grava as distâncias, os tempos brutos, as médias e o ambiente em
`resultados_p3/`. Cada média concluída usa dez chamadas sobre o mesmo grafo em
memória, com `perf_counter()`. Leitura, transposição, escrita e extração da amostra
ficam fora do cronômetro. `--limite-todos-pares` define o tamanho máximo para
essas execuções. O padrão é 2.000 vértices.

## Estudos de caso

| Grafo | Vértices | Arestas | 10 → 100 | 20 → 100 | 30 → 100 | Média (s) |
|---|---:|---:|---:|---:|---:|---:|
| W1 | 25.000 | 549.953 | −∞ | −∞ | −∞ | 0,354 |
| W2 | 25.000 | 824.964 | 10,47 | 8,48 | 8,71 | 1,227 |
| W3 | 100.000 | 6.099.941 | 4,63 | 5,42 | 4,67 | 2,992 |
| W4 | 1.000.000 | 30.999.978 | 9,04 | 8,83 | 9,23 | 13,721 |
| W5 | 10.000.000 | 39.999.995 | 37,85 | 42,63 | 37,86 | 14,821 |

Em W1, um ciclo negativo pode ser alcançado pelas três origens e a partir dele
é possível chegar a 100. Por isso, nenhuma das três distâncias tem mínimo
finito. A medição de W1 foi repetida numa sessão separada após tornar
determinística a seleção da aresta em empates com pesos negativos.

O menor grafo oficial tem 25.000 vértices. A implementação densa de
Floyd-Warshall usa cerca de 7,5 GB para as duas matrizes desse grafo, acima dos 4 GB de RAM da máquina.
Ela considera
até 15,6 trilhões de combinações por rodada. Para 10 milhões de vértices,
as matrizes exigiriam cerca de 1,2 PB. A matriz de distâncias do Bellman-Ford
para todos os pares também excede a RAM, começando em 5 GB. Os cinco grafos excederam o limite
configurado. As matrizes 5 × 5 solicitadas por Floyd-Warshall e os tempos
comparativos de todos os pares ficaram pendentes. `floyd_warshall.csv`
contém somente o cabeçalho e `medias.csv` registra as execuções omitidas.

Em pior caso, Bellman-Ford custa `O(V(V + E))` na versão CSR, com vetores
auxiliares lineares por destino, e pode terminar após poucas rodadas em certos
grafos. Repeti-lo para todos os destinos custa até `O(V²(V + E))`, com
`O(V²)` para armazenar as distâncias. Floyd-Warshall usa `O(V³)` de tempo e
`O(V²)` de memória. A fronteira e a parada antecipada podem reduzir bastante a
quantidade de relaxamentos em grafos esparsos. Os dados medidos vão até a consulta
para um destino e são insuficientes para ordenar o desempenho de todos os pares.
