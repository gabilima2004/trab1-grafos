from collections import deque

INFINITO = -1


def bfs_niveis(grafo, origem, alvo=None, coletar=False, nivel=None):
    """BFS usada como primitiva das distâncias.

    Retorna (nivel, mais_distante, alcancados, visitados). Com `alvo`,
    para assim que ele é descoberto; com `coletar`, devolve a lista dos
    vértices alcançados. O vetor `nivel` pode ser reaproveitado entre
    chamadas, mas deve chegar todo em INFINITO.
    """

    if nivel is None:
        nivel = [INFINITO] * (grafo.numero_vertices + 1)

    nivel[origem] = 0

    fila = deque([origem])

    mais_distante = origem
    alcancados = 1

    visitados = [origem] if coletar else None

    while fila:
        v = fila.popleft()

        if alvo is not None and v == alvo:
            break

        for w in grafo.vizinhos(v):
            if nivel[w] != INFINITO:
                continue

            nivel[w] = nivel[v] + 1
            alcancados += 1

            if coletar:
                visitados.append(w)

            if nivel[w] > nivel[mais_distante]:
                mais_distante = w

            fila.append(w)

    return nivel, mais_distante, alcancados, visitados


def distancia(grafo, u, v):
    """Distância (número de arestas do menor caminho) entre u e v.
    Retorna INFINITO se estiverem em componentes diferentes."""

    if u == v:
        return 0

    nivel, _, _, _ = bfs_niveis(grafo, u, alvo=v)

    return nivel[v]


def excentricidade(grafo, v):
    """Maior distância de v até um vértice alcançável a partir dele."""

    nivel, mais_distante, _, _ = bfs_niveis(grafo, v)

    return nivel[mais_distante], mais_distante


def diametro(grafo, mostrar_progresso=False):
    """Diâmetro exato: uma BFS por vértice, O(n * (n + m)).

    Em grafo desconexo, devolve a maior distância finita, ou seja, o
    maior diâmetro entre as componentes conexas.
    """

    maior = 0
    par = (None, None)

    for v in range(1, grafo.numero_vertices + 1):
        ecc, w = excentricidade(grafo, v)

        if ecc > maior:
            maior = ecc
            par = (v, w)

        if mostrar_progresso and v % 500 == 0:
            print(f"  diâmetro exato: {v}/{grafo.numero_vertices} vértices"
                  f" (máximo até agora = {maior})")

    return maior, par


def diametro_aproximado(grafo, repeticoes=10):
    """Aproximação do diâmetro por varredura dupla (double sweep).

    Em cada componente, parte de um vértice qualquer, acha o mais
    distante `a` e, a partir de `a`, o mais distante `b`, repetindo
    enquanto o valor melhorar. O resultado é um limite inferior do
    diâmetro e nunca menor que a metade dele.
    """

    n = grafo.numero_vertices

    visitado = bytearray(n + 1)

    # Reaproveitado por todas as BFS desta função.
    nivel = [INFINITO] * (n + 1)

    maior = 0
    par = (None, None)

    for v in range(1, n + 1):
        if visitado[v]:
            continue

        _, a, _, componente = bfs_niveis(grafo, v, coletar=True, nivel=nivel)

        for u in componente:
            visitado[u] = 1
            nivel[u] = INFINITO

        melhor_local = 0
        par_local = (v, a)
        origem = a

        for _ in range(repeticoes):
            niveis, b, _, visitados = bfs_niveis(
                grafo, origem, coletar=True, nivel=nivel
            )

            ecc = niveis[b]

            for u in visitados:
                nivel[u] = INFINITO

            if ecc <= melhor_local:
                break

            melhor_local = ecc
            par_local = (origem, b)
            origem = b

        if melhor_local > maior:
            maior = melhor_local
            par = par_local

    return maior, par
