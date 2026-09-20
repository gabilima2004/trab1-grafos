class Grafo:
    def __init__(self, numero_vertices, representacao="lista"):
        self.numero_vertices = numero_vertices
        self.representacao = representacao

        self.lista_adjacencia = None
        self.matriz_adjacencia = None

        if representacao == "lista":
            self.lista_adjacencia = [[] for _ in range(numero_vertices + 1)]
        else:
            self.matriz_adjacencia = [
                bytearray(numero_vertices + 1)
                for _ in range(numero_vertices + 1)
            ]

        self.graus = [0] * (numero_vertices + 1)

    def adicionar_aresta(self, u, v):
        if self.representacao == "lista":
            self.lista_adjacencia[u].append(v)
            self.lista_adjacencia[v].append(u)
        else:
            self.matriz_adjacencia[u][v] = 1
            self.matriz_adjacencia[v][u] = 1

        self.graus[u] += 1
        self.graus[v] += 1

    def vizinhos(self, u):
        if self.representacao == "lista":
            return self.lista_adjacencia[u]

        linha = self.matriz_adjacencia[u]

        return [v for v in range(1, self.numero_vertices + 1) if linha[v]]

    def grau(self, u):
        return self.graus[u]

    def obter_representacao(self):
        if self.representacao == "lista":
            return self.lista_adjacencia

        return self.matriz_adjacencia
