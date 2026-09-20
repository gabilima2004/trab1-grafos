class Grafo:
    def __init__(self, numero_vertices):
        self.numero_vertices = numero_vertices

        # Lista de adjacência
        self.lista_adjacencia = [[] for _ in range(numero_vertices + 1)]

        # Matriz de adjacência
        self.matriz_adjacencia = [
            [0] * (numero_vertices + 1)
            for _ in range(numero_vertices + 1)
        ]

    def adicionar_aresta(self, u, v):
        # Grafo não-direcionado:
        # a aresta aparece nos dois sentidos.

        self.lista_adjacencia[u].append(v)
        self.lista_adjacencia[v].append(u)

        self.matriz_adjacencia[u][v] = 1
        self.matriz_adjacencia[v][u] = 1

    def vizinhos(self, u):
        return self.lista_adjacencia[u]

    def grau(self, u):
        return len(self.lista_adjacencia[u])