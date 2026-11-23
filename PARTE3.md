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

PENDENTE — preenchido ao fim da medição (C blocado em W1 e W2).

W3 a W5 não cabem em memória: mesmo na versão inteira (distâncias e
predecessores em `int32`, já que n > 32.767), as matrizes exigiriam 80 GB,
8 TB e 800 TB.

### 3. Tempo médio (10 rodadas, segundos)

PENDENTE — preenchido ao fim da medição.

### 4. Bellman-Ford para todos os pares × Floyd-Warshall

PENDENTE — preenchido ao fim da medição, com Johnson como terceira referência e
a curva dos grafos sintéticos (500 a 4.000 vértices).
