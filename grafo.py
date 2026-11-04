from math import isfinite


class Grafo:
    def __init__(self, numero_vertices, representacao="lista", ponderado=False):
        if numero_vertices < 0 or representacao not in ("lista", "matriz"):
            raise ValueError("Número de vértices ou representação inválidos.")
        self.numero_vertices = numero_vertices
        self.representacao = representacao
        self.ponderado = ponderado
        self.tem_peso_negativo = False

        self.lista_adjacencia = None
        self.matriz_adjacencia = None

        if representacao == "lista":
            self.lista_adjacencia = [[] for _ in range(numero_vertices + 1)]
        else:
            self.matriz_adjacencia = [
                ([None] * (numero_vertices + 1) if ponderado
                 else bytearray(numero_vertices + 1))
                for _ in range(numero_vertices + 1)
            ]

        self.graus = [0] * (numero_vertices + 1)

    def validar_vertice(self, u):
        if not isinstance(u, int) or not 1 <= u <= self.numero_vertices:
            raise ValueError(f"Vértice {u} fora do intervalo 1..{self.numero_vertices}.")

    def adicionar_aresta(self, u, v, peso=None):
        self.validar_vertice(u)
        self.validar_vertice(v)
        if not self.ponderado and peso is not None:
            raise ValueError("Crie o grafo com ponderado=True para adicionar pesos.")
        peso = 1.0 if peso is None else float(peso)
        if not isfinite(peso):
            raise ValueError("O peso deve ser um número real finito.")
        self.tem_peso_negativo |= peso < 0
        if self.representacao == "lista":
            self.lista_adjacencia[u].append((v, peso) if self.ponderado else v)
            self.lista_adjacencia[v].append((u, peso) if self.ponderado else u)
        else:
            if self.ponderado:
                anterior = self.matriz_adjacencia[u][v]
                if anterior is None or peso < anterior:
                    self.matriz_adjacencia[u][v] = peso
                    self.matriz_adjacencia[v][u] = peso
                if anterior is not None:
                    return
                self.graus[u] += 1
                self.graus[v] += 1
                return
            self.matriz_adjacencia[u][v] = 1
            self.matriz_adjacencia[v][u] = 1

        self.graus[u] += 1
        self.graus[v] += 1

    def vizinhos(self, u):
        if self.representacao == "lista":
            if self.ponderado:
                return [v for v, _ in self.lista_adjacencia[u]]
            return self.lista_adjacencia[u]

        linha = self.matriz_adjacencia[u]

        return [v for v in range(1, self.numero_vertices + 1)
                if (linha[v] is not None if self.ponderado else linha[v])]

    def vizinhos_com_pesos(self, u):
        """Itera pelas arestas sem copiar a lista de adjacência."""
        if self.representacao == "lista":
            if self.ponderado:
                yield from self.lista_adjacencia[u]
            else:
                for v in self.lista_adjacencia[u]:
                    yield v, 1.0
        else:
            linha = self.matriz_adjacencia[u]
            for v in range(1, self.numero_vertices + 1):
                if self.ponderado:
                    if linha[v] is not None:
                        yield v, linha[v]
                elif linha[v]:
                    yield v, 1.0

    def grau(self, u):
        return self.graus[u]

    def obter_representacao(self):
        if self.representacao == "lista":
            return self.lista_adjacencia

        return self.matriz_adjacencia
