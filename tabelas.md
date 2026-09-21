## Memória e tempo de execução

| grafo | vértices | arestas | memória lista (MB) | memória matriz (MB) | BFS lista (s) | BFS matriz (s) | DFS lista (s) | DFS matriz (s) |
|---|---|---|---|---|---|---|---|---|
| grafo_1.txt.gz | 10000 | 109977 | 10.95 | 97.10 | 0.008668 | 1.230279 | 0.019419 | 1.287707 |
| grafo_2.txt.gz | 49948 | 1299794 | 113.47 | 2385.04 | 0.129329 | 14.396012 | 0.242965 | 14.222675 |
| grafo_3.txt.gz | 375000 | 765618 | 91.89 | - | 0.263438 | - | 0.298654 | - |
| grafo_4.txt.gz | 375000 | 8187427 | 716.70 | - | 1.928581 | - | 3.015766 | - |
| grafo_5.txt.gz | 4843750 | 13168928 | 1451.86 | - | 4.756777 | - | 5.638282 | - |
| grafo_6.txt.gz | 4843750 | 46469670 | 4354.55 | - | 12.497479 | - | 19.290787 | - |

## Distâncias, componentes e diâmetro

| grafo | d(10,20) | d(10,30) | d(20,30) | componentes | maior componente | menor componente | diâmetro aprox. | diâmetro exato |
|---|---|---|---|---|---|---|---|---|
| grafo_1.txt.gz | 3 | 3 | 4 | 1 | 10000 | 10000 | 4 | 5 |
| grafo_2.txt.gz | infinito (componentes diferentes) | infinito (componentes diferentes) | 3 | 10 | 25000 | 48 | 20 | - |
| grafo_3.txt.gz | 9 | infinito (componentes diferentes) | infinito (componentes diferentes) | 2 | 250000 | 125000 | 21 | - |
| grafo_4.txt.gz | 4 | 3 | 4 | 2 | 250000 | 125000 | 5 | - |
| grafo_5.txt.gz | infinito (componentes diferentes) | 9 | infinito (componentes diferentes) | 5 | 2500000 | 156250 | 59 | - |
| grafo_6.txt.gz | 5 | 5 | 5 | 5 | 2500000 | 156250 | 19 | - |

## Pai dos vértices 10, 20 e 30

**grafo_1.txt.gz**

- BFS a partir de 1: pai(10) = 2042 [nível 3], pai(20) = 8382 [nível 3], pai(30) = 8979 [nível 4]
- BFS a partir de 2: pai(10) = 8935 [nível 2], pai(20) = 7541 [nível 4], pai(30) = 8660 [nível 4]
- BFS a partir de 3: pai(10) = 7685 [nível 3], pai(20) = 9429 [nível 4], pai(30) = 5783 [nível 3]
- DFS a partir de 1: pai(10) = 3075 [nível 9233], pai(20) = 3575 [nível 9234], pai(30) = 6071 [nível 4699]
- DFS a partir de 2: pai(10) = 6552 [nível 4533], pai(20) = 9429 [nível 6828], pai(30) = 6071 [nível 6860]
- DFS a partir de 3: pai(10) = 2344 [nível 8547], pai(20) = 8781 [nível 9264], pai(30) = 6071 [nível 8048]

**grafo_2.txt.gz**

- BFS a partir de 1: pai(10) = -, pai(20) = -, pai(30) = -
- BFS a partir de 2: pai(10) = 31751 [nível 3], pai(20) = -, pai(30) = -
- BFS a partir de 3: pai(10) = -, pai(20) = 46738 [nível 3], pai(30) = 18855 [nível 3]
- DFS a partir de 1: pai(10) = -, pai(20) = -, pai(30) = -
- DFS a partir de 2: pai(10) = 18057 [nível 16225], pai(20) = -, pai(30) = -
- DFS a partir de 3: pai(10) = -, pai(20) = 887 [nível 8458], pai(30) = 32621 [nível 3484]

**grafo_3.txt.gz**

- BFS a partir de 1: pai(10) = -, pai(20) = -, pai(30) = 141597 [nível 14]
- BFS a partir de 2: pai(10) = 158403 [nível 8], pai(20) = 75471 [nível 9], pai(30) = -
- BFS a partir de 3: pai(10) = 158403 [nível 10], pai(20) = 319691 [nível 7], pai(30) = -
- DFS a partir de 1: pai(10) = -, pai(20) = -, pai(30) = 141597 [nível 69293]
- DFS a partir de 2: pai(10) = 19428 [nível 151888], pai(20) = 141526 [nível 110599], pai(30) = -
- DFS a partir de 3: pai(10) = 106718 [nível 67166], pai(20) = 75471 [nível 171152], pai(30) = -

**grafo_4.txt.gz**

- BFS a partir de 1: pai(10) = 194465 [nível 4], pai(20) = 274921 [nível 4], pai(30) = 136244 [nível 3]
- BFS a partir de 2: pai(10) = -, pai(20) = -, pai(30) = -
- BFS a partir de 3: pai(10) = -, pai(20) = -, pai(30) = -
- DFS a partir de 1: pai(10) = 272292 [nível 160404], pai(20) = 370783 [nível 223217], pai(30) = 129700 [nível 188681]
- DFS a partir de 2: pai(10) = -, pai(20) = -, pai(30) = -
- DFS a partir de 3: pai(10) = -, pai(20) = -, pai(30) = -

**grafo_5.txt.gz**

- BFS a partir de 1: pai(10) = 1888350 [nível 8], pai(20) = -, pai(30) = 2502539 [nível 9]
- BFS a partir de 2: pai(10) = -, pai(20) = -, pai(30) = -
- BFS a partir de 3: pai(10) = 3696745 [nível 9], pai(20) = -, pai(30) = 191713 [nível 9]
- DFS a partir de 1: pai(10) = 905955 [nível 1154139], pai(20) = -, pai(30) = 2502539 [nível 1783393]
- DFS a partir de 2: pai(10) = -, pai(20) = -, pai(30) = -
- DFS a partir de 3: pai(10) = 905955 [nível 1846333], pai(20) = -, pai(30) = 2502539 [nível 1978536]

**grafo_6.txt.gz**

- BFS a partir de 1: pai(10) = -, pai(20) = -, pai(30) = -
- BFS a partir de 2: pai(10) = 1677854 [nível 4], pai(20) = 4095628 [nível 5], pai(30) = 4231681 [nível 5]
- BFS a partir de 3: pai(10) = -, pai(20) = -, pai(30) = -
- DFS a partir de 1: pai(10) = -, pai(20) = -, pai(30) = -
- DFS a partir de 2: pai(10) = 4534830 [nível 515287], pai(20) = 623747 [nível 2138226], pai(30) = 2943822 [nível 1836075]
- DFS a partir de 3: pai(10) = -, pai(20) = -, pai(30) = -

