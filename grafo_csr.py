import gzip
import warnings
from math import isfinite

import numpy as np

TIPO_ARESTA = np.dtype([("u", np.int32), ("v", np.int32), ("peso", np.float64)])


class GrafoCSR:
    representacao = "csr"
    ponderado = True

    def __init__(self, numero_vertices, inicio, adjacentes, pesos):
        n = int(numero_vertices)
        if not 0 <= n <= np.iinfo(np.int32).max - 2:
            raise ValueError("Número de vértices inválido.")
        inicio = np.ascontiguousarray(inicio, dtype=np.int64)
        adjacentes = np.ascontiguousarray(adjacentes, dtype=np.int32)
        pesos = np.ascontiguousarray(pesos, dtype=np.float64)
        if (inicio.shape != (n + 2,) or adjacentes.shape != pesos.shape
                or adjacentes.ndim != 1 or adjacentes.size % 2
                or inicio[0] != 0 or inicio[1] != 0 or inicio[-1] != adjacentes.size
                or np.any(np.diff(inicio) < 0)):
            raise ValueError("Vetores CSR inconsistentes.")
        if adjacentes.size and (adjacentes.min() < 1 or adjacentes.max() > n):
            raise ValueError(f"Vizinho fora do intervalo 1..{n}.")
        if not np.isfinite(pesos).all():
            raise ValueError("O peso deve ser um número real finito.")

        self.numero_vertices = n
        self.numero_arestas = adjacentes.size // 2
        self.inicio = inicio
        self.adjacentes = adjacentes
        self.pesos = pesos
        self.tem_peso_negativo = bool((pesos < 0).any())
        self._inicio = memoryview(inicio)
        self._adjacentes = memoryview(adjacentes)
        self._pesos = memoryview(pesos)

    def validar_vertice(self, u):
        if not isinstance(u, (int, np.integer)) or not 1 <= u <= self.numero_vertices:
            raise ValueError(f"Vértice {u} fora do intervalo 1..{self.numero_vertices}.")

    def adicionar_aresta(self, u, v, peso=None):
        raise TypeError("GrafoCSR é somente leitura; monte-o a partir das arestas.")

    def vizinhos(self, u):
        return self._adjacentes[self._inicio[u]:self._inicio[u + 1]].tolist()

    def vizinhos_com_pesos(self, u):
        a = self._inicio[u]
        b = self._inicio[u + 1]
        return zip(self._adjacentes[a:b], self._pesos[a:b])

    def grau(self, u):
        return self._inicio[u + 1] - self._inicio[u]

    def obter_representacao(self):
        return self.inicio, self.adjacentes, self.pesos

    def bytes_ocupados(self):
        return self.inicio.nbytes + self.adjacentes.nbytes + self.pesos.nbytes


def montar_csr(numero_vertices, origens, destinos, pesos):
    origens = np.asarray(origens, dtype=np.int32)
    destinos = np.asarray(destinos, dtype=np.int32)
    pesos = np.asarray(pesos, dtype=np.float64)
    m = origens.size
    if destinos.size != m or pesos.size != m:
        raise ValueError("Vetores de arestas com tamanhos diferentes.")
    fontes = np.empty(2 * m, np.int32)
    fontes[0::2] = origens
    fontes[1::2] = destinos
    if m and (fontes.min() < 1 or fontes.max() > numero_vertices):
        raise ValueError(f"Vértice fora do intervalo 1..{numero_vertices}.")
    inicio = np.zeros(numero_vertices + 2, np.int64)
    np.cumsum(np.bincount(fontes, minlength=numero_vertices + 1), out=inicio[1:])
    ordem = np.argsort(fontes, kind="stable")
    del fontes
    alvos = np.empty(2 * m, np.int32)
    alvos[0::2] = destinos
    alvos[1::2] = origens
    adjacentes = alvos[ordem]
    del alvos
    pesos_csr = np.repeat(pesos, 2)[ordem]
    return GrafoCSR(numero_vertices, inicio, adjacentes, pesos_csr)


def _abrir(nome_arquivo):
    nome_arquivo = str(nome_arquivo)
    return gzip.open(nome_arquivo, "rb") if nome_arquivo.endswith(".gz") else open(nome_arquivo, "rb")


def _localizar_erro(nome_arquivo):
    with _abrir(nome_arquivo) as arquivo:
        numero_vertices = int(arquivo.readline())
        for numero_linha, linha in enumerate(arquivo, 2):
            campos = linha.split()
            if not campos:
                continue
            if len(campos) != 3:
                raise ValueError(f"Linha {numero_linha}: número de colunas inválido.")
            try:
                u, v, peso = int(campos[0]), int(campos[1]), float(campos[2])
            except ValueError as erro:
                raise ValueError(f"Linha {numero_linha}: {erro}") from erro
            for vertice in (u, v):
                if not 1 <= vertice <= numero_vertices:
                    raise ValueError(f"Linha {numero_linha}: Vértice {vertice} "
                                     f"fora do intervalo 1..{numero_vertices}.")
            if not isfinite(peso):
                raise ValueError(f"Linha {numero_linha}: O peso deve ser um número real finito.")


def _ler_numpy(nome_arquivo):
    with _abrir(nome_arquivo) as arquivo:
        try:
            numero_vertices = int(arquivo.readline())
        except ValueError as erro:
            raise ValueError("Linha 1: número de vértices inválido.") from erro
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", "loadtxt: input contained no data")
                arestas = np.loadtxt(arquivo, dtype=TIPO_ARESTA, comments=None, ndmin=1)
        except (ValueError, OverflowError) as erro:
            _localizar_erro(nome_arquivo)
            raise ValueError(f"Arquivo ponderado inválido: {erro}") from erro
    try:
        if not np.isfinite(arestas["peso"]).all():
            raise ValueError("O peso deve ser um número real finito.")
        return montar_csr(numero_vertices, arestas["u"], arestas["v"], arestas["peso"])
    except ValueError:
        _localizar_erro(nome_arquivo)
        raise


def ler_grafo_csr(nome_arquivo, leitor="numpy"):
    if leitor == "numpy":
        return _ler_numpy(nome_arquivo)
    if leitor == "c":
        from motor_c import ler_csr
        return ler_csr(nome_arquivo)
    raise ValueError("Leitor deve ser 'numpy' ou 'c'.")
