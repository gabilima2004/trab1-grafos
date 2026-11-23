# COS242 | Parte 3 — Caminhos mínimos com pesos negativos

Código-fonte da biblioteca em [trab1-grafos](https://github.com/gabilima2004/trab1-grafos),
branch `trabalho-p3`.

## O que a parte 3 acrescenta

| Requisito do enunciado | Onde está |
|---|---|
| Grafos direcionados com pesos (lista, matriz, CSR) | `ler_grafo(..., direcionado=True)`, `Grafo`, `GrafoCSR`, leitor C |
| BFS, DFS e Dijkstra em grafos direcionados | `busca.py`, `dfs.py`, `caminhos_minimos.py`, `motor_c.dijkstra_c` |
| Bellman-Ford até um destino, com árvore, ciclo negativo e duas otimizações | `caminhos_p3.bellman_ford`, `motor_c.bellman_ford_c` |
| Floyd-Warshall com árvores por origem, ciclo negativo e otimização de memória | `caminhos_p3.floyd_warshall`, `floyd_warshall_blocado`, `motor_c.floyd_warshall_c` |
| Extra para o estudo 4 | Johnson (`caminhos_p3.johnson`, `motor_c.johnson_c`) e Bellman-Ford para todos os pares |

## Representação

`ler_grafo(arquivo, representacao, direcionado=True)` lê cada linha como um
arco do primeiro para o segundo vértice. Lista, matriz e CSR guardam só os arcos
de saída quando o grafo é direcionado; o padrão continua não direcionado. O
leitor C (`ler_grafo_csr(..., leitor="c", direcionado=True, transposto=...)`)
monta o CSR original ou o transposto direto do arquivo, na mesma ordem do
leitor NumPy. No menu, `python main.py --direcionado` ativa essa leitura.

BFS, DFS e Dijkstra já percorriam os vizinhos de saída, então funcionam sem
mudança em grafos direcionados. Dijkstra recusa arestas negativas.
Componentes conexas e diâmetro recusam grafos direcionados.

## Bellman-Ford

O enunciado pede a distância **de todos os vértices até um destino**, a mesma
formulação de Kleinberg e Tardos (seção 6.8). O algoritmo roda no grafo
transposto a partir do destino, e o vetor de sucessores reconstrói as rotas no
sentido original. As duas otimizações são as do livro:

1. **Parada antecipada:** termina na primeira rodada sem nenhuma melhora.
2. **Relaxar só a partir de quem mudou:** cada rodada percorre apenas os arcos
   dos vértices cuja distância melhorou na rodada anterior. A memória fica em
   um vetor de distâncias, em vez da tabela n × n da recorrência.

Uma melhora na rodada `n` certifica um ciclo negativo. Para não rodar `n`
rodadas inteiras quando há ciclo, a cada 16 rodadas o grafo de sucessores é
inspecionado; um ciclo de peso negativo nele já é um certificado. Os vértices
que alcançam o ciclo e, por ele, o destino recebem `-inf`.

O resultado traz dois indicadores:

- `tem_ciclo_negativo`: existe ciclo negativo que alcança o destino.
- `ciclo_no_grafo` (com `verificar_grafo=True`): existe ciclo negativo em
  qualquer parte do grafo. A verificação usa uma raiz virtual ligada a todos
  os vértices com custo zero. Ela fica opcional para não dobrar o custo das
  medições por destino.

## Floyd-Warshall

A otimização de memória da aula é atualizar **uma única matriz** no lugar,
em vez de guardar uma matriz por valor de `k`: Θ(n²) de memória, em vez de
Θ(n³). A linha `u` da matriz de predecessores é a árvore de caminhos mínimos
com origem em `u` (0 indica ausência de predecessor). Um valor negativo na
diagonal indica ciclo negativo, e os pares cujo caminho pode passar por ele
recebem `-inf`.

Essa marcação é feita de uma vez: agrupamos os vértices de ciclo negativo com o
mesmo conjunto alcançável e fazemos dois produtos de matrizes booleanas
("alcança um ciclo" × "é alcançado a partir dele"). A versão anterior varria a
matriz inteira para cada vértice de ciclo, o que em W1 seria proibitivo.

### Quatro versões

O algoritmo é sempre Θ(n³), e nenhuma variante prática muda isso. O que muda é
o custo de cada passo e a memória. Comparamos quatro versões:

| Versão | Aritmética | Memória (n = 25.000) | Ideia |
|---|---|---:|---|
| Python clássico | `float64` | 7,5 GB | laço `k`-`i` em Python, linha inteira por operação NumPy |
| Python blocado | `float64` | 7,5 GB | faixas de 64 linhas por operação; resultado idêntico ao clássico |
| C clássico | `float64` | 7,5 GB | laço `k`-`i`-`j` vetorizado e paralelo; idêntico ao Python clássico |
| C blocado | `int32` | 3,75 GB | ladrilhos 256 × 256, inteiros, OpenMP, árvores reconstruídas no fim |

**Por que o clássico é lento mesmo em C.** Para cada `k`, ele percorre as duas
matrizes inteiras: 7,5 GB lidos e escritos por iteração, 25.000 vezes. O
gargalo é a memória, não o processador.

**O que o C blocado faz:**

- **Ladrilhos (Venkataraman, Sahni e Mukhopadhyay, 2003).** A matriz é dividida
  em blocos de 256 × 256 que cabem no cache. Cada rodada processa o bloco da
  diagonal, depois os blocos da mesma linha e coluna, e por fim os demais. A
  última fase não tem dependências entre blocos e é dividida entre os núcleos.
- **Pesos inteiros.** Todos os pesos de W1 e W2 têm duas casas decimais, então
  são multiplicados por 100 (`escala_inteira` escolhe a menor potência de 10
  que torna os pesos inteiros). Assim a aritmética é exata, sem ruído como
  `10.469999999999999`. A memória cai pela metade, e o AVX2 processa 8 valores
  por instrução em vez de 4.
- **Saturação.** Com ciclo negativo, os valores do Floyd-Warshall podem dobrar
  de tamanho a cada `k` e estourar 32 bits. As somas são limitadas a −2³⁰.
  Qualquer valor nesse piso só pode vir de um passeio com ciclo negativo, e
  esse par já seria marcado como `-inf`.
- **Árvores reconstruídas depois.** O laço cúbico só calcula distâncias. Depois
  dele, cada linha da árvore é obtida por uma busca em largura que segue só os
  arcos "justos" (`D[i][p] + w(p,j) == D[i][j]`). Isso só é confiável porque
  as distâncias são inteiras e exatas. Predecessores ficam em `int16` quando
  `n < 32.768`.

**Um problema que os testes encontraram.** Na ordem por blocos, uma célula pode
usar uma linha pivô que já melhorou por outro `k` da mesma rodada. As distâncias
continuam corretas, mas com **ciclos de peso zero** (W2 tem arcos de peso 0) a
cópia de predecessores pode fechar um laço na árvore. A reconstrução por busca
em largura elimina o problema na versão C. Na versão Python blocada, cada
linha pivô é copiada antes de ser usada, o que torna a execução idêntica à
clássica, bit a bit.

## Johnson (extra)

Johnson repondera o grafo uma vez com Bellman-Ford a partir de uma raiz
virtual, `w'(u,v) = w(u,v) + h(u) − h(v) ≥ 0`, e depois roda Dijkstra com heap
a partir de cada vértice. O custo fica em O(n·m·log n), bem menor que n³ em
grafos esparsos como W1 e W2. Com ciclo negativo, a reponderação é impossível:
Johnson apenas o reporta, sem calcular distâncias.

## Reprodução

```sh
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
make testes
python comparacao_todos_pares.py --tamanhos 500 1000 2000 4000
python comparacao_todos_pares.py grafo_W_1.txt.gz grafo_W_2.txt.gz grafo_W_3.txt.gz grafo_W_4.txt.gz grafo_W_5.txt.gz
python comparacao_todos_pares.py --conferir
```

`make testes` compila o motor C (GCC, zlib, OpenMP) e roda as suítes das partes
2 e 3. `test_todos_pares.py` confere:

- as versões Python e C entre si;
- a validade de toda árvore (o peso de cada rota é igual à distância);
- a saturação com ciclo negativo;
- o leitor C direcionado e o Dijkstra C em grafos direcionados;
- os valores conhecidos de W2.

`comparacao_todos_pares.py` grava um JSON por grafo em
`resultados_p3/todos_pares/` após cada rodada, então pode ser interrompido e
retomado com o mesmo comando. Leitura, montagem do CSR e transposição ficam
fora do cronômetro. A construção do resultado e a marcação de ciclos negativos
entram na medição. O fim da execução confere se todas as versões produziram as
mesmas amostras 5 × 5. O caminho antigo, só em Python e para máquinas com pouca
memória, continua descrito no [guia de experimentos](GUIA_EXPERIMENTOS_P3.md).

## Estudos de caso

Máquina: Intel Core Ultra 5 238V (8 núcleos, AVX2), 30 GB de RAM, Linux,
Python 3.14, GCC 15.2. Versões com 8 threads, salvo indicação.

### 1. Bellman-Ford até o vértice 100

| Grafo | Vértices | Arcos | 10 → 100 | 20 → 100 | 30 → 100 |
|---|---:|---:|---:|---:|---:|
| W1 | 25.000 | 549.953 | −∞ | −∞ | −∞ |
| W2 | 25.000 | 824.964 | 10,47 | 8,48 | 8,71 |
| W3 | 100.000 | 6.099.941 | 4,63 | 5,42 | 4,67 |
| W4 | 1.000.000 | 30.999.978 | 9,04 | 8,83 | 9,23 |
| W5 | 10.000.000 | 39.999.995 | 37,85 | 42,63 | 37,86 |

W1 tem um ciclo negativo que as três origens alcançam e a partir do qual se
chega a 100. Por isso nenhuma das distâncias tem mínimo finito; em W1 todos os
25.000 vértices recebem −∞ para esse destino.

### 2. Floyd-Warshall entre {10, 20, 30, 40, 50}

Distância da linha (origem) até a coluna (destino), calculada pelo C blocado.
O C clássico, o Bellman-Ford para todos os pares e o Johnson chegaram aos mesmos
valores (diferença máxima de 10⁻¹⁴, só de arredondamento do `float64`).

**W2** (sem ciclo negativo):

| | 10 | 20 | 30 | 40 | 50 |
|---|---:|---:|---:|---:|---:|
| **10** | 0 | 11,73 | 8,14 | 9,49 | 7,08 |
| **20** | 3,84 | 0 | 7,03 | 8,30 | 4,70 |
| **30** | 5,79 | 12,55 | 0 | 8,30 | 6,33 |
| **40** | 5,05 | 12,32 | 5,36 | 0 | 5,71 |
| **50** | 4,48 | 12,23 | 7,79 | 8,26 | 0 |

**W1:** o Floyd-Warshall encontra ciclo negativo, e os 25 pares, inclusive a
diagonal, valem −∞. Cada um dos cinco vértices alcança o ciclo e é alcançado a
partir dele, então nenhuma dessas distâncias tem mínimo finito. Isso confirma
o estudo 1.

W3 a W5 não cabem em memória: mesmo na versão inteira (distâncias e
predecessores em `int32`, já que n > 32.767), as matrizes exigiriam 80 GB,
8 TB e 800 TB.

### 3. Tempo médio (segundos)

Média de 10 rodadas, exceto o Floyd-Warshall C clássico (2 rodadas, por levar
cerca de uma hora cada). Desvio padrão entre parênteses.

| Grafo | Bellman-Ford (Python) | Bellman-Ford (C) | Floyd-Warshall C blocado | Floyd-Warshall C clássico |
|---|---:|---:|---:|---:|
| W1 | 0,206 (0,001) | 0,026 (0,000) | 527 (33) | 3.787 (38) |
| W2 | 0,055 (0,002) | 0,010 (0,000) | 429 (4) | 3.486 (41) |
| W3 | 0,433 (0,004) | 0,104 (0,000) | — | — |
| W4 | 3,56 (0,05) | 1,59 (0,00) | — | — |
| W5 | 5,76 (0,05) | 3,97 (0,03) | — | — |

O Bellman-Ford até um destino é rápido porque as duas otimizações cortam quase
todo o trabalho: as rodadas param assim que nada melhora, e cada rodada só
percorre os arcos de quem mudou. Em W1, a verificação periódica do grafo de
sucessores encontra o ciclo cedo, sem chegar à rodada n.

No Floyd-Warshall, a versão blocada foi **7,2× mais rápida** que a clássica em
W1 e **8,1×** em W2. As duas fazem as mesmas n³ = 1,6 × 10¹³ comparações; a
diferença vem só de como usam a memória.

O laço cúbico custa o mesmo em W1 e W2: ele não depende dos pesos nem do número
de arcos. Numa rodada isolada, feita depois do benchmark, o C blocado levou
434 s em W1 e 430 s em W2. A diferença real é a marcação de −∞: 13 s em W1,
em que todos os 625 milhões de pares recebem −∞, e zero em W2. O restante da
diferença na tabela é variação entre rodadas: as rodadas de W1 oscilaram entre
450 e 560 s (desvio de 33 s), e as de W2 ficaram entre 425 e 436 s.

O Floyd-Warshall em Python não rodou em W1 e W2. Medimos o custo real na matriz
de W2: 2,2 s por fase `k` densa na versão clássica e 80 s por rodada de 64 fases
na blocada. A clássica pula as linhas com `D[u][k] = ∞`, e, em média, 71% das
linhas estão ativas em W1 e 63% em W2. A estimativa é de 10,7 h (W1) e 9,6 h
(W2) por rodada na clássica, e 8,7 h na blocada, ou seja, de 3,5 a 4,5 dias para
dez rodadas (`resultados_p3/todos_pares/estimativa_fw_python.json`). Por isso ele
foi medido só nos sintéticos.

### 4. Bellman-Ford para todos os pares × Floyd-Warshall

Bellman-Ford para todos os pares roda o Bellman-Ford otimizado uma vez para cada
destino (25.000 execuções, em paralelo com 8 threads). Johnson entra como
terceira referência.

| Grafo | Bellman-Ford × n (C) | Johnson (C) | Floyd-Warshall C blocado | Floyd-Warshall C clássico |
|---|---:|---:|---:|---:|
| W1 | 163 | 0,04 (só detecta o ciclo) | 527 | 3.787 |
| W2 | 76 | **51** | 429 | 3.486 |

**Grafos sintéticos** (n vértices, 22n arcos com pesos de 0 a 10, média de 3
rodadas):

| n | FW Python clássico | FW Python blocado | FW C clássico 1T / 8T | FW C blocado 1T / 8T | BF × n Python / C | Johnson Python / C |
|---:|---:|---:|---:|---:|---:|---:|
| 500 | 0,64 | 0,29 | 0,046 / 0,092 | 0,042 / 0,036 | 0,46 / 0,010 | 1,51 / 0,013 |
| 1.000 | 3,04 | 2,12 | 0,47 / 0,91 | 0,24 / 0,12 | 1,79 / 0,045 | 6,53 / 0,056 |
| 2.000 | 15,1 | 15,4 | 4,44 / 3,41 | 1,51 / 0,53 | 6,63 / 0,18 | 28,0 / 0,23 |
| 4.000 | 89,9 | 75,7 | 37,3 / 21,6 | 9,98 / 3,11 | 27,4 / 0,83 | 119 / 1,07 |

**Quem ganhou e por quê.**

- **Em grafos esparsos, Bellman-Ford para todos os pares ganha do
  Floyd-Warshall**, mesmo com a melhor versão deste: 5,6× em W2, 3,2× em W1 e
  3,7× no sintético de 4.000 vértices. O Floyd-Warshall custa n³ qualquer que
  seja o número de arcos. O Bellman-Ford otimizado custa cerca de n · m ·
  (rodadas efetivas), e com m ≈ 22n a 33n e poucas rodadas efetivas isso fica
  bem abaixo de n³. Sem as otimizações (n − 1 rodadas completas por destino), o
  custo seria n² · m ≈ 5 × 10¹⁴ em W2, 30× pior que o Floyd-Warshall.
- **Johnson é o mais rápido quando não há ciclo negativo** (51 s em W2), porque
  troca as 25.000 execuções de Bellman-Ford por uma só, seguida de Dijkstra com
  heap, que não reprocessa vértices. Com ciclo negativo, ele só pode reportá-lo.
  W2 não tem nenhum arco negativo (W1 tem 4.998), então ali a reponderação é
  trivial e o Johnson equivale a rodar Dijkstra a partir de cada vértice.
- **O Floyd-Warshall vale a pena em grafos densos**, em que m se aproxima de n²
  e Bellman-Ford × n chegaria a n⁴. Também tem custo previsível e um laço
  simples, que se beneficia de vetorização e cache.
- **A versão clássica é limitada pela memória.** Com 8 threads, ela foi só
  1,7× mais rápida que com 1 em n = 4.000, e com n ≤ 1.000 foi até mais lenta.
  A versão blocada ganha 3,2× com as mesmas 8 threads, porque cada bloco é
  reutilizado 256 vezes a partir do cache.
- **Em Python, o bloqueio ajuda pouco** (2,2× em n = 500, 1,2× em n = 4.000 e
  nenhum ganho em n = 2.000), porque cada operação NumPy ainda percorre a memória principal. O
  ganho real veio do C: 29× entre o Python clássico e o C blocado em n = 4.000.
