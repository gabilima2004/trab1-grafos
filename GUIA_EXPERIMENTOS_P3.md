# Execução dos experimentos da Parte 3

Há dois caminhos:

- **Motor C (principal).** `comparacao_todos_pares.py` mede todas as versões
  de Floyd-Warshall, Bellman-Ford e Johnson. É o caminho dos resultados
  publicados em `resultados_p3/todos_pares/`. Exige Linux com GCC, zlib e
  OpenMP, e pelo menos 16 GB de RAM para W1 e W2.
- **Só Python (alternativo).** `benchmark_p3.py` foi feito para máquinas com
  pouca memória: planeja, estima e recusa casos que não cabem. Está descrito a
  partir de "Preparar a máquina para o caminho só Python".

## Caminho principal: motor C

```sh
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
make testes
```

`make testes` compila `c/libgrafos.so` com `-O2 -march=native -fopenmp` e roda
as suítes das partes 2 e 3. Coloque os `grafo_W_*.txt.gz` na raiz do projeto;
eles podem continuar compactados.

```sh
python comparacao_todos_pares.py --tamanhos 500 1000 2000 4000
python comparacao_todos_pares.py grafo_W_1.txt.gz grafo_W_2.txt.gz grafo_W_3.txt.gz grafo_W_4.txt.gz grafo_W_5.txt.gz
python comparacao_todos_pares.py --conferir
```

A primeira linha mede a curva em grafos sintéticos direcionados (22 arcos por
vértice, como W1, pesos de 0 a 10 com duas casas). Ela usa três rodadas por
versão, inclusive as versões Python e as versões C com uma thread. A segunda
linha mede os grafos oficiais com as rodadas padrão:

| Chave | Algoritmo | Rodadas |
|---|---|---:|
| `bellman_ford_py`, `bellman_ford_c` | Bellman-Ford até 100 (todos os grafos) | 10 |
| `fw_blocado_c` | Floyd-Warshall C blocado com inteiros | 10 |
| `bf_todos_c` | Bellman-Ford C para todos os destinos | 10 |
| `johnson_c` | Johnson em C | 10 |
| `fw_classico_c` | Floyd-Warshall C clássico | 2 |

O clássico em C fica com duas rodadas porque cada uma leva horas em W1 e W2;
o objetivo dele é mostrar o ganho da versão blocada. Os algoritmos de todos os
pares só rodam até `--limite-todos-pares` vértices (padrão 25.000), então W3
a W5 aparecem como omitidos. `--rodadas chave=N ...` troca o plano, e
`--threads N` fixa o número de threads (0 usa todos os núcleos).

Cada rodada concluída é gravada no JSON do grafo. Ctrl+C perde só a rodada em
curso, e repetir o comando retoma de onde parou. `--conferir` compara as
amostras 5 × 5 de todas as versões e termina com erro se alguma divergir.
Rode uma medição por vez e evite outras cargas na máquina durante a execução.

## Preparar a máquina para o caminho só Python

Use Python 3.11 ou superior e a dependência NumPy de `requirements.txt`.
Copie uma versão congelada dos arquivos desta árvore de trabalho, incluindo
os arquivos novos locais, e abra um terminal nessa pasta. Coloque os cinco
`grafo_W_*.txt.gz` originais em `dados/`. Eles podem permanecer compactados.
O motor C é opcional e não participa dos benchmarks desta seção.

```sh
python -m venv .venv
```

No PowerShell, ative com `.venv/Scripts/Activate.ps1`. Se a política do shell
impedir a ativação, use `.venv/Scripts/python.exe` no lugar de `python`.
No Linux, ative com `source .venv/bin/activate`.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -v
```

Sem a biblioteca nativa, seis testes do motor C são pulados. Em Linux com
`make`, GCC e os headers da zlib, `make testes` compila o motor e roda as
suítes, usando o Python do ambiente virtual. O novo cronômetro foi executado
em Windows. O caminho Linux usa `/proc/meminfo` e, quando disponível, limites
de cgroups v2.


## Calibrar e planejar antes de rodar

A calibração usa grafos sintéticos direcionados, conexos no sentido forte,
com 80, 160 e 320 vértices, 4 ou 16 arcos por vértice e pesos positivos.
Cada combinação executa os dois algoritmos de todos os pares dez vezes.
A geração dos grafos e a gravação ficam fora da janela medida.
O arquivo local identifica o sistema, o código, o NumPy e a máquina.

```sh
python calibracao_p3.py --saida medicoes/calibracao.json
python benchmark_p3.py dados/grafo_W_1.txt.gz floyd_warshall --planejar --calibracao medicoes/calibracao.json
python benchmark_p3.py dados/grafo_W_1.txt.gz bellman_ford_todos_pares --planejar --calibracao medicoes/calibracao.json
```

O modo de planejamento conta as linhas de arestas por leitura em blocos,
sem montar o grafo ou executar os algoritmos. O pré-teste de RAM inclui
estimativas para a preparação e as matrizes. O teste feito após carregar
o grafo é mais específico e ainda pode recusar a execução.

Em casos longos, o cronômetro exige a calibração local e a confirmação
explícita. O critério é mais de 2.000 vértices ou teto da estimativa
superior a 120 segundos para as rodadas restantes. Depois de avaliar o
plano, execute somente os casos compatíveis com o tempo e a memória
disponíveis.

```sh
python benchmark_p3.py dados/grafo_W_1.txt.gz floyd_warshall --calibracao medicoes/calibracao.json --confirmar-custo --saida medicoes/W1-fw.json
python benchmark_p3.py dados/grafo_W_1.txt.gz bellman_ford_todos_pares --calibracao medicoes/calibracao.json --confirmar-custo --saida medicoes/W1-bf-pares.json
```

Repita para W2 se o prazo comportar. Use o mesmo caminho de saída para
retomar na mesma versão do código. Envie os JSONs das medições, do
planejamento se o redirecionou para um arquivo, e da calibração local.
Se o computador travar ou o processo terminar à força, o último JSON
publicado contém as rodadas já gravadas. A rodada em curso pode precisar
ser refeita por inteiro.

A faixa extrapola o custo a partir dos dois casos de 320 vértices.
Para Floyd-Warshall, multiplica pelo cubo da razão de tamanhos. Para
Bellman-Ford, usa a razão dos termos V(V + E) e supõe número comparável
de rodadas de relaxamento por destino. Para uma consulta, divide a
estimativa de todos os pares por V. A faixa é um cenário ilustrativo,
sem garantia de prazo. Densidade, alcance, ciclos negativos,
comportamento do cache e número de relaxamentos podem mudar muito o
custo. A calibração não reproduz a topologia ou os pesos de W1 a W5.
Em W1, o pós-processamento de ciclos negativos de Floyd-Warshall não é
representado pelos grafos sintéticos positivos.

## Executar um grafo e um algoritmo

Os comandos abaixo usam W1. Troque o sufixo `1` no caminho do grafo e na
saída para outro arquivo oficial. Execute um processo de medição por vez.

```sh
python benchmark_p3.py dados/grafo_W_1.txt.gz bellman_ford --destino 100 --calibracao medicoes/calibracao.json --confirmar-custo --saida medicoes/W1-bf.json
python benchmark_p3.py dados/grafo_W_1.txt.gz floyd_warshall --calibracao medicoes/calibracao.json --confirmar-custo --saida medicoes/W1-fw.json
python benchmark_p3.py dados/grafo_W_1.txt.gz bellman_ford_todos_pares --calibracao medicoes/calibracao.json --confirmar-custo --saida medicoes/W1-bf-pares.json
```

Use a terceira linha com `--fluxo` e outro arquivo, como
`medicoes/W1-bf-pares-fluxo.json`, para calcular todas as colunas descartando
cada vetor após o uso e retendo só a amostra 5 × 5. A variante densa retém
a matriz durante cada rodada. Declare qual variante foi usada na comparação.
Na contagem do tempo entram a execução e a construção do resultado em RAM.
Leitura, preparação do CSR e gravação ficam fora. A extração da amostra ocorre
fora do cronômetro na variante densa. No modo em fluxo, copiar as cinco
colunas da amostra enquanto elas estão disponíveis faz parte da execução.

O script reserva 20% da memória disponível detectada e confere estimativas
antes da leitura do CSR e antes das rodadas. `--memoria-gib N` aplica um teto
adicional. Em sistemas sem detecção, informe o teto explicitamente. As estimativas
incluem folga para o grafo e temporários e podem recusar um caso que caberia.
`--confirmar-custo` confirma o trabalho dos algoritmos de todos os pares
acima de 2.000 vértices. O limite de memória continua ativo.

## Pausar, retomar e enviar

O terminal mostra o início de cada rodada e confirma quando ela foi gravada.
Para interromper, use **Ctrl+C**. Cada rodada concluída e gravada fica no
JSON, e uma rodada interrompida antes desse ponto recomeça inteira. Repita
o mesmo comando com a mesma saída para retomar. O script compara a soma
SHA-256 do grafo, as versões do código, a identificação do ambiente e os
parâmetros do algoritmo antes de combinar medições. Um bloqueio do sistema
operacional impede duas instâncias de escrever no mesmo arquivo.

Envie os **JSONs** da pasta `medicoes/`, inclusive os incompletos ou
bloqueados. O arquivo completo tem `estado: concluido`, exatamente 10
valores em `tempos_s` e uma `media_s`. Arquivos parciais têm média nula.
`eventos` registra recusas de memória, erros e interrupções durante a execução.
O campo `amostra` guarda apenas as respostas publicadas para conferência.
Para comparar os algoritmos, use medições do mesmo grafo, da mesma máquina
e da mesma versão do código.

## Orçamento de recursos

A tabela dá apenas o tamanho das matrizes finais, em unidades decimais.
Cada fase ainda precisa do grafo e dos vetores temporários. A coluna
"clássico" usa distâncias `float64` e predecessores `int32`. A coluna
"blocado" usa distâncias `int32` e predecessores `int16` (ou `int32` acima de
32.767 vértices).

| Grafo | Vértices | Floyd clássico | Floyd C blocado | Bellman-Ford denso | Combinações V³ por rodada de Floyd |
|---|---:|---:|---:|---:|---:|
| W1, W2 | 25.000 | 7,50 GB | 3,75 GB | 5,00 GB | 1,56 × 10¹³ |
| W3 | 100.000 | 120 GB | 80 GB | 80 GB | 10¹⁵ |
| W4 | 1.000.000 | 12 TB | 8 TB | 8 TB | 10¹⁸ |
| W5 | 10.000.000 | 1,2 PB | 0,8 PB | 0,8 PB | 10²¹ |

Johnson em C guarda distâncias `float64` e predecessores `int32`, como o
clássico.

- **Uma consulta Bellman-Ford.** As dez rodadas já foram obtidas na
  máquina local para W1 a W5. Refaça na máquina da dupla se quiser uma
  série na mesma máquina dos demais benchmarks.
- **Todos os pares em W1 e W2.** Comece por esses grafos em uma máquina com
  pelo menos 16 GiB e memória livre suficiente no momento da execução. Isso
  indica espaço para as matrizes, sem garantir conclusão em prazo útil.
  Para planejar Bellman-Ford, multiplicar a consulta até 100 pelo número
  de destinos daria aproximadamente 2,5 h em W1 e 8,5 h em W2 por rodada
  na máquina local, caso os demais destinos tivessem o mesmo custo.
  Esses valores são extrapolações, e os custos podem variar por destino.
- **W3.** Uma máquina de 192 GiB ou mais pode comportar as matrizes de
  Floyd-Warshall se houver RAM livre suficiente. O tempo cúbico ainda
  torna as dez rodadas incertas. A extrapolação da consulta de
  Bellman-Ford até 100 dá cerca de 83 h por rodada na máquina local.
- **W4 e W5.** O tamanho das matrizes e o trabalho tornam a abordagem
  densa impraticável em computadores usuais. O modo `--fluxo` economiza
  memória no Bellman-Ford, mas ainda executa (V) consultas completas por
  rodada. Os tempos brutos de uma consulta dão extrapolações da ordem de
  meses ou anos por rodada nessa máquina, sujeitas à variação de custos.
  A conclusão de desempenho deve se limitar aos grafos com dez rodadas
  efetivamente medidas para ambos os algoritmos.

Se um caso exceder o orçamento, registre o requisito, a estimativa e o
estado real. As tabelas seletivas abaixo podem ser incluídas com o
método explicitado. A aceitação desse complemento ou de um subconjunto
dos benchmarks oficiais deve ser combinada com o professor.

## Reproduzir as tabelas seletivas

As tabelas em `resultados_p3/amostrais/` são de **Bellman-Ford por destino**.
A validação original usou Dijkstra em C para W2 a W5 e um certificado de
ciclo negativo e alcance para W1. O script usa Dijkstra Python por padrão
para a conferência dos pesos não negativos, e aceita
`--validar-dijkstra c` quando o motor foi compilado.

```sh
python distancias_amostrais_p3.py dados/grafo_W_1.txt.gz --saida amostras/W1.csv --ciclo 9931 12129 9931
python distancias_amostrais_p3.py dados/grafo_W_2.txt.gz --saida amostras/W2.csv
```

Repita o segundo comando para W3 a W5, com arquivos de saída distintos.
O CSV auxiliar `.validacao.csv` indica como cada célula foi conferida.

## Precisão e ciclos

`bellman_ford(grafo, destino)` indica em `tem_ciclo_negativo` os ciclos que
alcançam aquele destino. Com `verificar_grafo=True`, o resultado também traz
`ciclo_no_grafo`, que cobre todas as componentes. `tem_ciclo_negativo_global`
faz só essa verificação: parte de distâncias iniciais zero para todos os
vértices, o equivalente a uma raiz virtual. O teste global fica fora das
medições por destino para preservar o custo de cada benchmark.
`bellman_ford_c` aceita os mesmos parâmetros.

As versões Python, o Floyd-Warshall C clássico, o Bellman-Ford C e o Johnson
usam `float64`. O Floyd-Warshall C blocado usa inteiros na escala dos pesos
(×100 em W1 e W2): é exato e recusa pesos que não cabem em 32 bits
(`escala_inteira`). A aritmética `float64` pode perder uma melhora pequena perto de
um valor muito grande, por exemplo, ao somar `-1` a `1e16`. O caso afeta a
detecção por relaxamento e está fora da escala observada nas consultas
oficiais. Os resultados finitos das tabelas foram conferidos por Dijkstra
com tolerância numérica. As entradas `-inf` foram conferidas com um ciclo
de custo estritamente negativo e caminhos de acesso. Os dados publicados
mantêm os valores de máquina dos algoritmos.
