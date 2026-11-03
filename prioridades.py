"""Filas de prioridade intercambiáveis para Dijkstra (vértices 1..n)."""

from math import inf


class FilaVetor:
    def __init__(self, distancias):
        self.distancias = distancias
        self.ativos = bytearray(len(distancias))

    def atualizar(self, vertice):
        self.ativos[vertice] = 1

    def extrair_minimo(self):
        menor, melhor = None, inf
        for v in range(1, len(self.distancias)):
            if self.ativos[v] and self.distancias[v] < melhor:
                menor, melhor = v, self.distancias[v]
        if menor is not None:
            self.ativos[menor] = 0
        return menor


class HeapIndexado:
    """Heap binário com uma entrada por vértice e decrease-key O(log n).

    posicao[v] permite localizar e subir v após uma redução de distância.
    Não acumula entradas antigas nem usa busca linear para atualizar chaves.
    """

    def __init__(self, distancias):
        self.distancias = distancias
        self.heap = []
        self.posicao = [-1] * len(distancias)

    def _menor(self, u, v):
        return (self.distancias[u], u) < (self.distancias[v], v)

    def _trocar(self, i, j):
        self.heap[i], self.heap[j] = self.heap[j], self.heap[i]
        self.posicao[self.heap[i]] = i
        self.posicao[self.heap[j]] = j

    def atualizar(self, vertice):
        i = self.posicao[vertice]
        if i == -1:
            i = len(self.heap)
            self.heap.append(vertice)
            self.posicao[vertice] = i
        while i > 0:
            pai = (i - 1) // 2
            if not self._menor(self.heap[i], self.heap[pai]):
                break
            self._trocar(i, pai)
            i = pai

    def extrair_minimo(self):
        if not self.heap:
            return None
        minimo = self.heap[0]
        ultimo = self.heap.pop()
        self.posicao[minimo] = -1
        if self.heap:
            self.heap[0] = ultimo
            self.posicao[ultimo] = 0
            i = 0
            while 2 * i + 1 < len(self.heap):
                filho = 2 * i + 1
                if filho + 1 < len(self.heap) and self._menor(self.heap[filho + 1], self.heap[filho]):
                    filho += 1
                if not self._menor(self.heap[filho], self.heap[i]):
                    break
                self._trocar(i, filho)
                i = filho
        return minimo
