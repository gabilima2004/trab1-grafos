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
    ciclo_no_grafo: bool | None = None

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


def bellman_ford(grafo, destino, *, transposto=None, verificar_grafo=False):
    """Calcula caminhos ate destino, com ciclo negativo detectavel se alcanca destino.

    transposto pode ser fornecido para reutilizar a preparacao em varias chamadas.
    Sucessores ausentes sao representados por None (lista/matriz) ou 0 (CSR).
    A distancia e -inf se um caminho ate destino pode passar por ciclo negativo.
    """
    grafo.validar_vertice(destino)
    reverso = transpor(grafo) if transposto is None else transposto
    resultado = _bellman_ford(reverso, destino)
    if verificar_grafo:
        resultado.ciclo_no_grafo = (resultado.tem_ciclo_negativo
                                    or _bellman_ford(reverso, None).tem_ciclo_negativo)
    return resultado


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


INF_INTEIRO = 0x3FFFFFFF
NEG_INTEIRO = -INF_INTEIRO


@dataclass
class ResultadoTodosPares:
    distancias: object
    predecessores: object
    tem_ciclo_negativo: bool
    escala: int | None = None

    def _exigir_distancias(self):
        if self.distancias is None:
            raise ValueError("Ciclo negativo: as distancias nao foram calculadas.")

    def distancia(self, origem, destino):
        self._exigir_distancias()
        valor = self.distancias[origem, destino]
        if self.escala is None:
            return float(valor)
        if valor == INF_INTEIRO:
            return inf
        if valor == NEG_INTEIRO:
            return -inf
        return int(valor) / self.escala

    def submatriz(self, vertices):
        import numpy as np

        self._exigir_distancias()
        bloco = self.distancias[np.ix_(vertices, vertices)]
        if self.escala is None:
            return bloco.astype(np.float64)
        saida = bloco / self.escala
        saida[bloco == INF_INTEIRO] = inf
        saida[bloco == NEG_INTEIRO] = -inf
        return saida

    def caminho(self, origem, destino):
        self._exigir_distancias()
        n = self.distancias.shape[0] - 1
        if not (1 <= origem <= n and 1 <= destino <= n):
            raise ValueError("Origem ou destino invalido.")
        if self.predecessores is None:
            raise ValueError("Este resultado nao guarda as arvores de caminhos minimos.")
        if self.distancia(origem, destino) in (inf, -inf):
            return []
        return reconstruir_caminho(self.predecessores[origem], origem, destino)


ResultadoFloydWarshall = ResultadoTodosPares


def marcar_ciclos_negativos(distancias, predecessores, infinito, marcador, faixa=1024):
    import numpy as np

    negativos = np.flatnonzero(distancias.diagonal()[1:] < 0) + 1
    if not negativos.size:
        return False
    tamanho = distancias.shape[1]
    alcance = np.packbits(distancias[negativos] != infinito, axis=1)
    grupos, rotulos = np.unique(alcance, axis=0, return_inverse=True)
    destinos = np.unpackbits(grupos, axis=1, count=tamanho).astype(np.float32)
    membros = np.zeros((negativos.size, len(grupos)), np.float32)
    membros[np.arange(negativos.size), rotulos.ravel()] = 1
    for inicio in range(0, distancias.shape[0], faixa):
        linhas = slice(inicio, inicio + faixa)
        chegam = (distancias[linhas][:, negativos] != infinito).astype(np.float32) @ membros
        afetados = (chegam > 0).astype(np.float32) @ destinos > 0
        distancias[linhas][afetados] = marcador
        predecessores[linhas][afetados] = 0
    return True


def _matrizes_iniciais(grafo):
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
    return distancias, predecessores


def floyd_warshall(grafo):
    """Calcula distancias e predecessores indexados por origem e destino."""
    import numpy as np

    distancias, predecessores = _matrizes_iniciais(grafo)
    tamanho = distancias.shape[0]
    candidatas = np.empty(tamanho)
    melhores = np.empty(tamanho, dtype=bool)
    with np.errstate(invalid="ignore"):
        for k in range(1, tamanho):
            dist_k = distancias[k].copy()
            pais_k = predecessores[k].copy()
            for u in np.flatnonzero(distancias[:, k] != inf):
                np.add(distancias[u, k], dist_k, out=candidatas)
                np.less(candidatas, distancias[u], out=melhores)
                np.copyto(distancias[u], candidatas, where=melhores)
                np.copyto(predecessores[u], pais_k, where=melhores)

    ciclo = marcar_ciclos_negativos(distancias, predecessores, inf, -inf)
    return ResultadoTodosPares(distancias, predecessores, ciclo)


def _relaxar_faixa(distancias, predecessores, i0, i1, k0, k1, linhas_k, pais_k):
    import numpy as np

    linhas = distancias[i0:i1]
    pais = predecessores[i0:i1]
    candidatas = np.empty_like(linhas)
    melhores = np.empty(linhas.shape, dtype=bool)
    for k in range(k0, k1):
        if i0 == k0:
            linhas_k[k - k0] = distancias[k]
            pais_k[k - k0] = predecessores[k]
        np.add(linhas[:, k, None], linhas_k[k - k0], out=candidatas)
        np.less(candidatas, linhas, out=melhores)
        np.copyto(linhas, candidatas, where=melhores)
        np.copyto(pais, pais_k[k - k0], where=melhores)


def floyd_warshall_blocado(grafo, bloco=64):
    import numpy as np

    if bloco < 1:
        raise ValueError("O bloco deve ser positivo.")
    distancias, predecessores = _matrizes_iniciais(grafo)
    tamanho = distancias.shape[0]
    linhas_k = np.empty((bloco, tamanho))
    pais_k = np.empty((bloco, tamanho), dtype=predecessores.dtype)
    with np.errstate(invalid="ignore"):
        for k0 in range(1, tamanho, bloco):
            k1 = min(k0 + bloco, tamanho)
            _relaxar_faixa(distancias, predecessores, k0, k1, k0, k1, linhas_k, pais_k)
            for i0 in range(1, tamanho, bloco):
                if i0 != k0:
                    _relaxar_faixa(distancias, predecessores, i0, min(i0 + bloco, tamanho),
                                   k0, k1, linhas_k, pais_k)

    ciclo = marcar_ciclos_negativos(distancias, predecessores, inf, -inf)
    return ResultadoTodosPares(distancias, predecessores, ciclo)


def escala_inteira(pesos, numero_vertices, limite=2 ** 29):
    import numpy as np

    pesos = np.asarray(pesos, dtype=np.float64)
    maximo = float(np.abs(pesos).max()) if pesos.size else 0.0
    for casas in range(7):
        escala = 10 ** casas
        valores = pesos * escala
        if np.all(np.abs(valores - np.round(valores)) <= 1e-6):
            if maximo * escala * max(numero_vertices - 1, 1) >= limite:
                raise ValueError("Pesos grandes demais para distancias inteiras de 32 bits.")
            return escala
    raise ValueError("Pesos com mais de seis casas decimais: use o Floyd-Warshall classico.")


def _arcos(grafo):
    import numpy as np

    if grafo.representacao == "csr":
        origens = np.repeat(np.arange(grafo.numero_vertices + 1, dtype=np.int32),
                            np.diff(grafo.inicio))
        return origens, grafo.adjacentes, grafo.pesos
    origens, destinos, pesos = [], [], []
    for u in range(1, grafo.numero_vertices + 1):
        for v, peso in grafo.vizinhos_com_pesos(u):
            origens.append(u)
            destinos.append(v)
            pesos.append(peso)
    return (np.asarray(origens, np.int32), np.asarray(destinos, np.int32),
            np.asarray(pesos, np.float64))


def johnson(grafo):
    import numpy as np
    from caminhos_minimos import dijkstra
    from grafo_csr import montar_csr

    potencial = _bellman_ford(grafo, None)
    if potencial.tem_ciclo_negativo:
        return ResultadoTodosPares(None, None, True)
    h = np.asarray(potencial.distancias, dtype=np.float64)
    n = grafo.numero_vertices
    origens, destinos, pesos = _arcos(grafo)
    ajustados = np.maximum(pesos + h[origens] - h[destinos], 0.0)
    reponderado = montar_csr(n, origens, destinos, ajustados, direcionado=True)
    distancias = np.full((n + 1, n + 1), inf)
    predecessores = np.zeros((n + 1, n + 1), dtype=np.int32)
    for s in range(1, n + 1):
        d, pais = dijkstra(reponderado, s, "heap")
        d = np.asarray(d, dtype=np.float64)
        finitos = d != inf
        distancias[s, finitos] = d[finitos] - h[s] + h[finitos]
        predecessores[s] = [p or 0 for p in pais]
    return ResultadoTodosPares(distancias, predecessores, False)
