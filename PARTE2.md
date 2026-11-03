# Parte 2 — implementação e guia

## O que o enunciado pede

1. Representar grafos não direcionados com pesos reais nas arestas.
2. Calcular as distâncias de uma origem para todos os vértices e a árvore
   de caminhos mínimos, usando Dijkstra com vetor e com heap.
3. Recusar caminhos mínimos se existir peso negativo no grafo.
4. Produzir as tabelas de caminhos de 10 até 20, 30, 40, 50 e 60, comparar
   os tempos das duas implementações e consultar a rede de pesquisadores.

O código não depende de pacotes externos. Os grafos ponderados oficiais e
o arquivo que relaciona pesquisadores a índices não estão neste repositório.
Assim, as medições e respostas oficiais ainda dependem desses dados. Não
use os grafos ou as tabelas da parte 1 como resultados da parte 2.

## Como executar

Abra o menu existente:

```bash
python main.py
```

Informe `exemplo_p2.txt`, escolha lista ou matriz e depois a opção **7**.
Escolha a origem `1` e a implementação desejada. O programa grava
`caminhos_heap_1.txt` ou `caminhos_vetor_1.txt`, com uma linha por vértice:
`vertice pai distancia`. A raiz e os inalcançáveis têm pai `0` no arquivo;
os inalcançáveis têm distância `inf`. Depois é possível consultar um destino.
A opção **3** também calcula uma rota ponderada, usando heap.
BFS e DFS continuam disponíveis e seus níveis contam arestas, independentemente
dos pesos. A opção de diâmetro informa que sua implementação é para grafos
sem pesos.

O exemplo tem seis vértices, sendo o sexto isolado. A distância de 1 a 3
é aproximadamente `4.1`, pelo caminho `1 → 2 → 5 → 4 → 3`.
O arquivo usa pesos não negativos para permitir executar Dijkstra. Para
testar a recusa, troque um peso por um número negativo.

Uso da biblioteca:

```python
from entrada_saida import ler_grafo
from caminhos_minimos import dijkstra, reconstruir_caminho, salvar_caminhos

grafo = ler_grafo("exemplo_p2.txt", "lista")
distancias, pais = dijkstra(grafo, 1, "heap")  # ou "vetor"
print(distancias[3])
print(reconstruir_caminho(pais, 1, 3))
salvar_caminhos("arvore_minima.txt", 1, distancias, pais)
```

## O que foi alterado e por quê

### `grafo.py`: pesos e compatibilidade

O construtor ganhou `ponderado=False`. Uma chamada antiga como `Grafo(5)`
continua criando o grafo sem pesos da parte 1. Para criar manualmente um
grafo ponderado:

```python
from grafo import Grafo
grafo = Grafo(5, "lista", ponderado=True)
grafo.adicionar_aresta(1, 2, 0.1)
```

Na lista ponderada, cada entrada é uma tupla `(vizinho, peso)` e a aresta
é inserida nas duas direções. Na matriz ponderada, cada célula é o peso ou
`None` quando não existe aresta. Essa distinção permite peso zero, que não
pode ser confundido com ausência de aresta. A matriz sem pesos continua
usando `bytearray`, como antes.

`vizinhos(u)` continua retornando apenas os identificadores para manter
BFS, DFS e componentes compatíveis. `vizinhos_com_pesos(u)` percorre pares
de vizinho e peso, sem copiar a lista ponderada. Dijkstra usa essa interface
e funciona com ambas as representações.

Os índices são validados no intervalo `1..n`. Os pesos usam `float` e devem
ser finitos: `NaN` e infinito são recusados. Pesos negativos são aceitos no
grafo e registrados em `tem_peso_negativo`, permitindo recusar Dijkstra
sem percorrer novamente todas as arestas a cada busca. Esse registro cobre
também componentes desconectadas da origem.

A lista preserva arestas paralelas. A matriz representa uma aresta por par
e mantém o menor peso entre duplicatas, suficiente para caminhos mínimos;
seus graus contam essa única aresta. Laços contribuem duas vezes para o grau.
O registro de peso negativo é conservador e permanece ativo após a inserção.
Use `adicionar_aresta` para construir o grafo: modificar diretamente as
estruturas internas pode desatualizar graus e esse registro.

### `entrada_saida.py`: leitura dos dois formatos

A primeira linha continua sendo o número de vértices. A primeira linha de
aresta identifica o formato: duas colunas para grafos sem pesos ou três
colunas para grafos ponderados. As demais linhas devem seguir o mesmo
formato; erros informam o número da linha. Arquivos `.txt.gz` continuam
aceitos e linhas vazias são ignoradas.

O parâmetro opcional `ponderado=True` exige três colunas. Os estudos de
caso usam essa opção para evitar medir acidentalmente arquivos da parte 1.
Em arquivos sem arestas, o padrão é não ponderado, mas é possível forçar
`ponderado=True`.

### `prioridades.py`: duas formas de escolher a menor estimativa

As duas estruturas compartilham o vetor de distâncias de Dijkstra e
oferecem `atualizar(v)` e `extrair_minimo()`:

- `FilaVetor` marca os vértices ativos e percorre o vetor ao extrair o
  menor. A atualização custa O(1) e a extração custa O(n).
- `HeapIndexado` mantém um heap binário de vértices e um vetor
  `posicao[v]`. Quando uma distância diminui, encontra a posição em O(1)
  e sobe o vértice em O(log n). A extração também custa O(log n).

O heap mantém no máximo uma entrada por vértice. Não usa inserções repetidas
com prioridades antigas. Isso atende à exigência de modificação eficiente
de chaves do enunciado. Em empates, as duas estruturas escolhem o menor
identificador de vértice para tornar o comportamento reproduzível.

### `caminhos_minimos.py`: um único algoritmo

`dijkstra(grafo, origem, implementacao)` executa estes passos:

1. Valida origem, implementação e ausência de pesos negativos.
2. Inicializa as distâncias com infinito, os pais com `None` e a origem com zero.
3. Ativa a origem na estrutura escolhida.
4. Extrai o vértice com menor estimativa e finaliza sua distância.
5. Para cada vizinho, calcula `distancia[u] + peso`. Se o resultado melhora
   a estimativa de um vértice ainda não finalizado, atualiza distância,
   pai e prioridade.
6. Termina quando não há vértices ativos e retorna `(distancias, pais)`.

Todo esse fluxo é compartilhado. Apenas a classe da fila muda. Os vetores
têm tamanho `n + 1`, com a posição zero sem uso, seguindo os índices dos
arquivos. A árvore é representada por `pais[v]`: seguir esses pais de um
destino até a raiz reconstrói a rota. `reconstruir_caminho` devolve `[]`
para inalcançáveis e `[origem]` para a própria raiz. `salvar_caminhos`
grava distâncias e pais, sem multiplicar espaço armazenando uma rota
completa para cada destino.

Com lista de adjacência, o vetor custa O(n² + m), enquanto o heap custa
O((n + m) log n); ambos usam O(n) de memória auxiliar. A representação do
grafo ocupa O(n + m) na lista e O(n²) na matriz. Na matriz, percorrer os
vizinhos custa O(n) por vértice, de modo que o heap também pode exigir
O(n² + (n + m) log n). A lista é o padrão dos experimentos.

Pesos zero são aceitos porque Dijkstra é correto para pesos não negativos.
Pesos negativos geram a mensagem solicitada pelo enunciado. Se houver
mais de uma rota ótima, basta retornar uma delas. Os resultados usam
ponto flutuante e podem apresentar arredondamento binário, como
`4.1000000000000005`; os estudos de caso formatam até 12 algarismos
significativos. Somas extremamente grandes podem exceder a faixa de `float`.

### `main.py`: integração com o menu

Foi adicionada a opção 7 para escolher a implementação de Dijkstra,
salvar a árvore e consultar uma rota. A opção 3 reconhece grafos ponderados.
A opção 4 evita apresentar o diâmetro em número de arestas como se fosse
um diâmetro ponderado. Erros de valor durante as opções são exibidos sem
encerrar o menu. Os demais algoritmos da parte 1 foram mantidos.

O `README.md` aponta para este guia e a `.gitignore` passou a ignorar os
arquivos `caminhos_heap_*.txt` e `caminhos_vetor_*.txt` gerados pelo menu,
assim como já fazia com as árvores de BFS e DFS. `exemplo_p2.txt` fornece
um exemplo pequeno para testar sem os dados oficiais e `test_parte2.py`
contém as verificações descritas ao final deste documento.

## Estudos de caso dos grafos ponderados

Após obter os arquivos oficiais, execute, por exemplo:

```bash
python experimentos_p2.py grafo_peso_1.txt.gz grafo_peso_2.txt.gz --k 100
```

O resultado é `tabelas_p2.md`, separado de `tabelas.md` da parte 1.
Para um teste inicial mais curto, escolha `--k 3`. É necessário ter pelo
menos 60 vértices para os destinos exigidos e `1 <= k <= n`.

Para cada grafo, o programa calcula uma única árvore a partir de 10 e
extrai as cinco rotas. Em seguida sorteia `k` origens distintas, com
semente 242 por padrão. As duas implementações usam exatamente as mesmas
origens. A ordem de execução alterna a cada origem para reduzir o viés da
ordem. O tempo é medido por `perf_counter` em torno da chamada completa
a Dijkstra, incluindo sua inicialização; leitura, escrita, formatação e
comparação de resultados ficam fora do cronômetro.

O programa verifica se as distâncias das duas implementações coincidem
dentro de tolerância numérica e informa o progresso a cada origem. A
média amostral é `tempo_total / k`. A tabela inclui tempo total, tempo
médio, representação, semente e origens para permitir repetir o estudo.
Cada grafo concluído é gravado antes de começar o seguinte. O vetor pode
ser lento em grafos grandes devido ao custo quadrático; não é omitido
automaticamente, pois sua comparação é requisito da parte 2.

## Estudo da rede de colaboração

O enunciado fornecido não especifica o formato do arquivo de nomes. Por
isso, a consulta aceita um mapeamento explícito em JSON UTF-8:

```json
{
  "Edsger W. Dijkstra": 1,
  "Alan M. Turing": 2,
  "J. B. Kruskal": 3,
  "Jon M. Kleinberg": 4,
  "Éva Tardos": 5,
  "Daniel R. Figueiredo": 6
}
```

**Esses índices são apenas ilustrativos.** Converta o arquivo oficial para
o formato `{nome: índice}` preservando seus índices reais. Inclua também
os demais pesquisadores para apresentar os intermediários pelo nome.
Se algum intermediário não tiver nome no JSON, a saída mostra seu índice.
Nomes e índices duplicados são recusados. Os seis nomes exigidos devem
estar presentes e a grafia é comparada exatamente, incluindo acentos.

```bash
python colaboracao.py rede.txt.gz pesquisadores.json
```

O programa executa Dijkstra com heap uma vez a partir de Edsger W.
Dijkstra e grava `colaboracao_p2.md`, contendo as cinco distâncias e rotas
com nomes. Os pesos do arquivo são usados diretamente: o enunciado já
informa que são inversamente proporcionais à quantidade de coautorias,
portanto não se aplica outra inversão.

## Verificação e entrega

```bash
python -m unittest -v test_parte2
```

Os testes cobrem as duas representações e implementações, atualização de
chaves e posições do heap, peso zero, laços, arestas paralelas, vértices
isolados, recusa de negativos inclusive em outra componente, leitura
compactada, formatos inválidos, preservação de BFS/DFS/componentes,
gravação da árvore e os dois estudos de caso. Grafos aleatórios são
comparados com Bellman-Ford implementado apenas como oráculo de teste;
ele não é uma funcionalidade pública de caminhos com pesos negativos.
Além das distâncias, os testes conferem o custo das rotas reconstruídas.

Para concluir a entrega acadêmica, ainda é preciso executar os programas
com os dados oficiais e elaborar o relatório com até cinco páginas,
contendo decisões de implementação, tabelas e URL do código-fonte. A
apresentação deve ter até oito minutos. Este documento explica o código
e serve de apoio; não substitui o relatório com os resultados oficiais.
