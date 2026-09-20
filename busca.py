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