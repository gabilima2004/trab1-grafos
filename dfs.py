def DFS(grafo, v_inicial):
    pai = {}
    nivel = {v_inicial: 0}
    explorado = set()

    pilha = [(v_inicial, None)]

    while pilha:
        v, p = pilha.pop()

        if v in explorado:
            continue

        explorado.add(v)

        if p is not None:
            pai[v] = p
            nivel[v] = nivel[p] + 1

        for w in reversed(grafo.vizinhos(v)):
            if w not in explorado:
                pilha.append((w, v))

    return pai, nivel


def componentes_dfs(grafo):
    visitado = [False] * (grafo.numero_vertices + 1)
    componentes = []

    for v in range(1, grafo.numero_vertices + 1):
        if visitado[v]:
            continue

        _, nivel = DFS(grafo, v)

        c = sorted(nivel.keys())

        for u in c:
            visitado[u] = True

        componentes.append(c)

    componentes.sort(key=len, reverse=True)

    tamanhos = [len(c) for c in componentes]

    return len(componentes), tamanhos, componentes
