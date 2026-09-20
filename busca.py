from collections import deque


def BFS(grafo, v_inicial):
    fila = deque([v_inicial])

    pai = {}
    nivel = {v_inicial: 0}
    descobertos = {v_inicial}

    while fila:
        v = fila.popleft()

        for i in grafo.lista_adjacencia[v]:
            if i in descobertos:
                continue

            pai[i] = v
            nivel[i] = nivel[v] + 1

            descobertos.add(i)
            fila.append(i)

    return pai, nivel

def componentes(grafo):
    
    n_explorado = set(range(1, grafo.numero_vertices + 1))
    
    componentes = []

    while n_explorado:
        v = next(iter(n_explorado))

        pai, _ = BFS(grafo, v)

        c = [v]
        n_explorado.remove(v)

        for i in pai:
            n_explorado.remove(i)
            c.append(i)

        componentes.append(c)

    componentes.sort(key=len, reverse=True)

    tamanhos = []

    for c in componentes:
        tamanhos.append(len(c))

    num_componentes = len(componentes)

    return num_componentes, tamanhos, componentes