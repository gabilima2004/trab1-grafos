def num_arestas(grafo):
    total = 0

    for i in range(1, grafo.numero_vertices + 1):
        total += grafo.grau(i)

    return total // 2


def grau_min(grafo):
    g = grafo.grau(1)

    for i in range(2, grafo.numero_vertices + 1):
        if grafo.grau(i) < g:
            g = grafo.grau(i)

    return g


def grau_max(grafo):
    g = grafo.grau(1)

    for i in range(2, grafo.numero_vertices + 1):
        if grafo.grau(i) > g:
            g = grafo.grau(i)

    return g


def grau_medio(grafo):
    total = 0

    for i in range(1, grafo.numero_vertices + 1):
        total += grafo.grau(i)

    return total / grafo.numero_vertices


def mediana(grafo):
    graus = []

    for i in range(1, grafo.numero_vertices + 1):
        graus.append(grafo.grau(i))

    graus.sort()

    n = len(graus)

    if n % 2 == 1:
        return graus[n // 2]

    return (graus[n // 2 - 1] + graus[n // 2]) / 2