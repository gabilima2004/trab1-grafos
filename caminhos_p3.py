"""Caminhos minimos em grafos com pesos positivos ou negativos."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum, inf

from caminhos_minimos import reconstruir_caminho


def transpor(grafo):
    """Inverte as arestas direcionadas, preservando a numeracao dos vertices."""
    if not grafo.direcionado:
        return grafo
    n = grafo.numero_vertices
    if grafo.representacao == "csr":
        import numpy as np
        from grafo_csr import montar_csr

        fontes = np.repeat(np.arange(n + 1, dtype=np.int32), np.diff(grafo.inicio))
        return montar_csr(n, grafo.adjacentes, fontes, grafo.pesos, direcionado=True)

    from grafo import Grafo

    reverso = Grafo(n, ponderado=grafo.ponderado, direcionado=True)
    for u in range(1, n + 1):
        for v, peso in grafo.vizinhos_com_pesos(u):
            reverso.adicionar_aresta(v, u, peso if grafo.ponderado else None)
    return reverso


@dataclass
class ResultadoBellmanFord:
    destino: int | None
    distancias: Sequence[float]
    sucessores: Sequence[int | None]
    tem_ciclo_negativo: bool

    def caminho(self, origem):
        """Retorna a rota ate o destino ou [] sem minimo finito."""
        if not 1 <= origem < len(self.distancias):
            raise ValueError("Origem invalida.")
        if self.distancias[origem] in (inf, -inf):
            return []
        return reconstruir_caminho(self.sucessores, self.destino, origem)[::-1]


def _ciclos_negativos(sucessores, pesos):
    """Encontra ciclos de peso negativo no grafo atual de sucessores."""
    vistos = bytearray(len(sucessores))
    negativos = []
    for raiz in range(1, len(sucessores)):
        u = raiz
        while u and not vistos[u]:
            vistos[u] = 1
            u = sucessores[u]
        if u and vistos[u] == 1:
            ciclo = [u]
            v = sucessores[u]
            while v != u:
                ciclo.append(v)
                v = sucessores[v]
            if fsum(pesos[v] for v in ciclo) < 0:
                negativos.extend(ciclo)
        u = raiz
        while u and vistos[u] == 1:
            vistos[u] = 2
            u = sucessores[u]
    return negativos


def _marcar_afetados(sementes, vizinhos, distancias, sucessores, sem_sucessor=None):
    pendentes = list(sementes)
    for u in pendentes:
        distancias[u] = -inf
        sucessores[u] = sem_sucessor
    while pendentes:
        u = pendentes.pop()
        for v, _ in vizinhos(u):
            if distancias[v] != -inf:
                distancias[v] = -inf
                sucessores[v] = sem_sucessor
                pendentes.append(v)


def _bellman_ford_csr(reverso, destino):
    import numpy as np

    n = reverso.numero_vertices
    distancias = np.full(n + 1, inf)
    sucessores = np.zeros(n + 1, dtype=np.int32)
    pesos_sucessores = np.zeros(n + 1) if reverso.tem_peso_negativo else None
    if destino is None:
        distancias[1:] = 0
        fronteira = np.arange(1, n + 1, dtype=np.int32)
    else:
        distancias[destino] = 0
        fronteira = np.array([destino], dtype=np.int32)
    atualizados = np.zeros(n + 1, dtype=bool)
    tem_ciclo = False
    inicio = reverso.inicio

    for rodada in range(1, n + 1):
        valores = distancias[fronteira]
        atualizados.fill(False)
        # Divide a expansao da fronteira para limitar os vetores temporarios.
        for primeiro in range(0, fronteira.size, 16384):
            faixa = slice(primeiro, primeiro + 16384)
            fontes = fronteira[faixa]
            inicios = inicio[fontes]
            quantidades = inicio[fontes + 1] - inicios
            fim = np.cumsum(quantidades)
            indices = np.repeat(inicios + quantidades - fim, quantidades)
            indices += np.arange(indices.size)
            alvos = reverso.adjacentes[indices]
            pesos = reverso.pesos[indices]
            candidatas = np.repeat(valores[faixa], quantidades) + pesos
            anteriores = distancias[alvos]
            np.minimum.at(distancias, alvos, candidatas)
            melhores = (candidatas < anteriores) & (candidatas == distancias[alvos])
            alterados = alvos[melhores]
            sucessores_candidatos = np.repeat(fontes, quantidades)[melhores]
            if pesos_sucessores is not None:
                # Seleciona a mesma aresta para o sucessor e seu peso em caso de empate.
                alterados, escolhidos = np.unique(alterados, return_index=True)
                sucessores_candidatos = sucessores_candidatos[escolhidos]
                pesos_sucessores[alterados] = pesos[melhores][escolhidos]
            sucessores[alterados] = sucessores_candidatos
            atualizados[alterados] = True

        fronteira = np.flatnonzero(atualizados).astype(np.int32)
        if not fronteira.size:
            break
        if rodada == n:
            negativos = fronteira
        elif pesos_sucessores is not None and rodada % 16 == 0:
            negativos = _ciclos_negativos(sucessores, pesos_sucessores)
        else:
            continue
        if len(negativos):
            if destino is None:
                return ResultadoBellmanFord(None, distancias, sucessores, True)
            _marcar_afetados(negativos, reverso.vizinhos_com_pesos,
                             distancias, sucessores, sem_sucessor=0)
            fronteira = fronteira[distancias[fronteira] != -inf]
            tem_ciclo = True
            if not fronteira.size:
                break

    return ResultadoBellmanFord(destino, distancias, sucessores, tem_ciclo)


def bellman_ford(grafo, destino, *, transposto=None):
    """Calcula caminhos ate destino, com ciclo negativo detectavel se alcanca destino.

    transposto pode ser fornecido para reutilizar a preparacao em varias chamadas.
    Sucessores ausentes sao representados por None (lista/matriz) ou 0 (CSR).
    A distancia e -inf se um caminho ate destino pode passar por ciclo negativo.
    """
    grafo.validar_vertice(destino)
    reverso = transpor(grafo) if transposto is None else transposto
    return _bellman_ford(reverso, destino)


def tem_ciclo_negativo_global(grafo):
    """Detecta ciclos em qualquer componente, com uma raiz virtual de custo zero."""
    if not grafo.tem_peso_negativo:
        return False
    # Distancias iniciais zero equivalem a ja ter relaxado as arestas virtuais.
    # A orientacao original serve, pois toda componente agora e alcancavel.
    return _bellman_ford(grafo, None).tem_ciclo_negativo


def _bellman_ford(reverso, destino):
    if reverso.representacao == "csr":
        return _bellman_ford_csr(reverso, destino)
    n = reverso.numero_vertices
    distancias = [inf] * (n + 1)
    sucessores = [None] * (n + 1)
    if destino is None:
        distancias[1:] = [0.0] * n
        fronteira = range(1, n + 1)
    else:
        distancias[destino] = 0.0
        fronteira = [destino]
    vizinhos = reverso.vizinhos_com_pesos

    pesos = [0.0] * (n + 1) if reverso.tem_peso_negativo else None
    tem_ciclo = False
    for rodada in range(1, n + 1):
        atualizados = set()
        # Captura os valores antes da rodada para limitar o numero de arestas.
        valores = [distancias[u] for u in fronteira]
        for u, distancia in zip(fronteira, valores):
            for v, peso in vizinhos(u):
                candidata = distancia + peso
                if candidata < distancias[v]:
                    distancias[v] = candidata
                    sucessores[v] = u
                    if pesos is not None:
                        pesos[v] = peso
                    atualizados.add(v)

        if atualizados and rodada == n:
            # Uma melhoria na n-esima rodada certifica um ciclo negativo.
            if destino is None:
                return ResultadoBellmanFord(None, distancias, sucessores, True)
            _marcar_afetados(atualizados, vizinhos, distancias, sucessores)
            tem_ciclo = True
        elif atualizados and pesos is not None and rodada % 16 == 0:
            # Um ciclo de peso negativo nos sucessores ja e um certificado.
            negativos = _ciclos_negativos(sucessores, pesos)
            if negativos:
                if destino is None:
                    return ResultadoBellmanFord(None, distancias, sucessores, True)
                _marcar_afetados(negativos, vizinhos, distancias, sucessores)
                atualizados = {v for v in atualizados if distancias[v] != -inf}
                tem_ciclo = True
        if not atualizados:
            break
        fronteira = atualizados

    return ResultadoBellmanFord(destino, distancias, sucessores, tem_ciclo)


@dataclass
class ResultadoFloydWarshall:
    distancias: object
    predecessores: object
    tem_ciclo_negativo: bool

    def caminho(self, origem, destino):
        """Retorna a rota ou [] sem minimo finito."""
        n = self.distancias.shape[0] - 1
        if not (1 <= origem <= n and 1 <= destino <= n):
            raise ValueError("Origem ou destino invalido.")
        if self.distancias[origem, destino] in (inf, -inf):
            return []
        return reconstruir_caminho(self.predecessores[origem], origem, destino)


def floyd_warshall(grafo):
    """Calcula distancias e predecessores indexados por origem e destino."""
    import numpy as np

    tamanho = grafo.numero_vertices + 1
    distancias = np.full((tamanho, tamanho), inf, dtype=np.float64)
    predecessores = np.zeros((tamanho, tamanho), dtype=np.int32)
    for u in range(1, tamanho):
        distancias[u, u] = 0
        for v, peso in grafo.vizinhos_com_pesos(u):
            if peso < distancias[u, v]:
                distancias[u, v] = peso
                predecessores[u, v] = u

    candidatas = np.empty(tamanho)
    melhores = np.empty(tamanho, dtype=bool)
    for k in range(1, tamanho):
        dist_k = distancias[k].copy()
        pais_k = predecessores[k].copy()
        for u in np.flatnonzero(distancias[:, k] != inf):
            np.add(distancias[u, k], dist_k, out=candidatas)
            np.less(candidatas, distancias[u], out=melhores)
            np.copyto(distancias[u], candidatas, where=melhores)
            np.copyto(predecessores[u], pais_k, where=melhores)

    negativos = np.flatnonzero(distancias.diagonal() < 0)
    for k in negativos:
        destinos = np.flatnonzero(distancias[k] != inf)
        for u in np.flatnonzero(distancias[:, k] != inf):
            distancias[u, destinos] = -inf
            predecessores[u, destinos] = 0

    return ResultadoFloydWarshall(distancias, predecessores, bool(negativos.size))
