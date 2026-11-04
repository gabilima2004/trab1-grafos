import ctypes
import os
from collections import namedtuple
from pathlib import Path

import numpy as np

from caminhos_minimos import MENSAGEM_PESO_NEGATIVO
from grafo_csr import GrafoCSR

CAMINHO_BIBLIOTECA = Path(os.environ.get("GRAFOS_BIBLIOTECA")
                          or Path(__file__).resolve().parent / "c" / "libgrafos.so")
FILAS = {"vetor": 0, "heap": 1}
_ERRO_ARQUIVO, _ERRO_MEMORIA = 1, 3
_biblioteca = None

ExecucaoC = namedtuple("ExecucaoC", "distancias pais segundos extracoes atualizacoes")


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
                                       ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64),
                                       ctypes.POINTER(ctypes.c_double)]
    biblioteca.gr_dijkstra.restype = ctypes.c_int
    biblioteca.gr_compilacao.argtypes = []
    biblioteca.gr_compilacao.restype = ctypes.c_char_p
    _biblioteca = biblioteca
    return biblioteca


def compilacao():
    return _carregar().gr_compilacao().decode()


def ler_csr(nome_arquivo):
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
        inicio = np.empty(n + 2, np.int64)
        adjacentes = np.empty(2 * m, np.int32)
        pesos = np.empty(2 * m, np.float64)
        if biblioteca.gr_montar_csr(leitura, inicio, adjacentes, pesos) != 0:
            raise MemoryError("Memória insuficiente para montar o CSR.")
    finally:
        biblioteca.gr_liberar_leitura(leitura)
    return GrafoCSR(n, inicio, adjacentes, pesos)


def executar_c(grafo, origem, implementacao="heap", limite_segundos=0.0, contar=False):
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
    atualizacoes = ctypes.c_int64()
    segundos = ctypes.c_double()
    codigo = biblioteca.gr_dijkstra(n, grafo.inicio, grafo.adjacentes, grafo.pesos, int(origem),
                                    FILAS[implementacao], distancias, pais, float(limite_segundos),
                                    ctypes.byref(extracoes),
                                    ctypes.byref(atualizacoes) if contar else None,
                                    ctypes.byref(segundos))
    if codigo == _ERRO_MEMORIA:
        raise MemoryError("Memória insuficiente para o Dijkstra em C.")
    if codigo != 0:
        raise RuntimeError(f"gr_dijkstra devolveu o código {codigo}.")
    return ExecucaoC(distancias, pais, segundos.value, extracoes.value,
                     atualizacoes.value if contar else None)


def dijkstra_c(grafo, origem, implementacao="heap"):
    execucao = executar_c(grafo, origem, implementacao)
    return execucao.distancias, execucao.pais
