"""Motor C: leitura e Dijkstra compilados (c/libgrafos.so), chamados via ctypes.

Compile com `make`. As funções trabalham sobre os mesmos vetores numpy de
GrafoCSR, sem cópia. O laço de Dijkstra e as duas filas (vetor e heap
indexado) em c/grafos.c espelham caminhos_minimos.py e prioridades.py:
mesma ordem de extração por (distância, vértice) e mesmas somas em ponto
flutuante. Assim, os dois motores produzem distâncias e pais idênticos e a
comparação de tempos mede apenas a linguagem e a fila de prioridade.
"""

import ctypes
import os
from collections import namedtuple
from pathlib import Path

import numpy as np

from caminhos_minimos import MENSAGEM_PESO_NEGATIVO
from grafo_csr import GrafoCSR

CAMINHO_BIBLIOTECA = Path(__file__).resolve().parent / "c" / "libgrafos.so"
FILAS = {"vetor": 0, "heap": 1}
_ERRO_ARQUIVO, _ERRO_MEMORIA = 1, 3
_biblioteca = None

# segundos: tempo medido dentro do C; extracoes: vértices extraídos da fila.
ExecucaoC = namedtuple("ExecucaoC", "distancias pais segundos extracoes")


def disponivel():
    return CAMINHO_BIBLIOTECA.exists()


def _carregar():
    global _biblioteca
    if _biblioteca is not None:
        return _biblioteca
    if not disponivel():
        raise RuntimeError("Motor C não compilado: rode `make` na pasta do projeto.")
    biblioteca = ctypes.CDLL(str(CAMINHO_BIBLIOTECA))

    def vetor(tipo):
        return np.ctypeslib.ndpointer(tipo, ndim=1, flags="C_CONTIGUOUS")

    biblioteca.gr_ler_arestas.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int),
                                          ctypes.c_char_p, ctypes.c_size_t]
    biblioteca.gr_ler_arestas.restype = ctypes.c_void_p
    biblioteca.gr_leitura_vertices.argtypes = [ctypes.c_void_p]
    biblioteca.gr_leitura_vertices.restype = ctypes.c_int32
    biblioteca.gr_leitura_arestas.argtypes = [ctypes.c_void_p]
    biblioteca.gr_leitura_arestas.restype = ctypes.c_int64
    biblioteca.gr_montar_csr.argtypes = [ctypes.c_void_p, vetor(np.int64), vetor(np.int32),
                                         vetor(np.float64)]
    biblioteca.gr_montar_csr.restype = ctypes.c_int
    biblioteca.gr_liberar_leitura.argtypes = [ctypes.c_void_p]
    biblioteca.gr_liberar_leitura.restype = None
    biblioteca.gr_dijkstra.argtypes = [ctypes.c_int32, vetor(np.int64), vetor(np.int32),
                                       vetor(np.float64), ctypes.c_int32, ctypes.c_int,
                                       vetor(np.float64), vetor(np.int32), ctypes.c_double,
                                       ctypes.POINTER(ctypes.c_int64),
                                       ctypes.POINTER(ctypes.c_double)]
    biblioteca.gr_dijkstra.restype = ctypes.c_int
    biblioteca.gr_compilacao.argtypes = []
    biblioteca.gr_compilacao.restype = ctypes.c_char_p
    _biblioteca = biblioteca
    return biblioteca


def compilacao():
    """Compilador e opções com que c/libgrafos.so foi gerada."""
    return _carregar().gr_compilacao().decode()


def ler_csr(nome_arquivo):
    """Lê um grafo ponderado (.txt ou .txt.gz) direto para GrafoCSR, em C."""
    biblioteca = _carregar()
    codigo = ctypes.c_int()
    erro = ctypes.create_string_buffer(1024)
    leitura = biblioteca.gr_ler_arestas(os.fsencode(nome_arquivo), ctypes.byref(codigo),
                                        erro, len(erro))
    if not leitura:
        texto = erro.value.decode("utf-8", "replace")
        if codigo.value == _ERRO_MEMORIA:
            raise MemoryError(texto)
        if codigo.value == _ERRO_ARQUIVO:
            raise OSError(texto)
        raise ValueError(texto)
    try:
        n = biblioteca.gr_leitura_vertices(leitura)
        m = biblioteca.gr_leitura_arestas(leitura)
        # O Python aloca o CSR e fica dono da memória; o C só preenche.
        inicio = np.empty(n + 2, np.int64)
        adjacentes = np.empty(2 * m, np.int32)
        pesos = np.empty(2 * m, np.float64)
        if biblioteca.gr_montar_csr(leitura, inicio, adjacentes, pesos) != 0:
            raise MemoryError("Memória insuficiente para montar o CSR.")
    finally:
        biblioteca.gr_liberar_leitura(leitura)
    return GrafoCSR(n, inicio, adjacentes, pesos)


def executar_c(grafo, origem, implementacao="heap", limite_segundos=0.0):
    """Dijkstra no motor C, com as mesmas validações de caminhos_minimos.dijkstra.

    Devolve ExecucaoC(distancias, pais, segundos, extracoes): vetores numpy
    com n + 1 posições, em que pais usa 0, e não None, para a origem e para
    os inalcançáveis. limite_segundos > 0 interrompe a execução no prazo
    (execução parcial, para estimar o tempo de execuções longas demais).
    """
    if not isinstance(grafo, GrafoCSR):
        raise TypeError("O motor C requer um GrafoCSR: use ler_grafo(arquivo, 'csr').")
    grafo.validar_vertice(origem)
    if grafo.tem_peso_negativo:
        raise ValueError(MENSAGEM_PESO_NEGATIVO)
    if implementacao not in FILAS:
        raise ValueError("Implementação deve ser 'vetor' ou 'heap'.")
    biblioteca = _carregar()
    n = grafo.numero_vertices
    distancias = np.empty(n + 1, np.float64)
    pais = np.empty(n + 1, np.int32)
    extracoes = ctypes.c_int64()
    segundos = ctypes.c_double()
    codigo = biblioteca.gr_dijkstra(n, grafo.inicio, grafo.adjacentes, grafo.pesos, int(origem),
                                    FILAS[implementacao], distancias, pais, float(limite_segundos),
                                    ctypes.byref(extracoes), ctypes.byref(segundos))
    if codigo == _ERRO_MEMORIA:
        raise MemoryError("Memória insuficiente para o Dijkstra em C.")
    if codigo != 0:
        raise RuntimeError(f"gr_dijkstra devolveu o código {codigo}.")
    return ExecucaoC(distancias, pais, segundos.value, extracoes.value)


def dijkstra_c(grafo, origem, implementacao="heap"):
    """Mesma interface de caminhos_minimos.dijkstra: devolve (distancias, pais)."""
    execucao = executar_c(grafo, origem, implementacao)
    return execucao.distancias, execucao.pais
