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
    def matriz(tipo):
        return np.ctypeslib.ndpointer(tipo, ndim=2, flags="C_CONTIGUOUS")

    csr = [ctypes.c_int32, vetor(np.int64), vetor(np.int32), vetor(np.float64)]
    biblioteca.gr_montar_csr_direcionado.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                     vetor(np.int64), vetor(np.int32),
                                                     vetor(np.float64)]
    biblioteca.gr_montar_csr_direcionado.restype = ctypes.c_int
    biblioteca.gr_floyd_warshall_classico.argtypes = csr + [matriz(np.float64), matriz(np.int32),
                                                            ctypes.c_int]
    biblioteca.gr_floyd_warshall_blocado.argtypes = csr + [ctypes.c_double, matriz(np.int32),
                                                           ctypes.c_void_p, ctypes.c_int,
                                                           ctypes.c_int32, ctypes.c_int]
    biblioteca.gr_bellman_ford.argtypes = csr + [ctypes.c_int32, vetor(np.float64),
                                                 vetor(np.int32), ctypes.POINTER(ctypes.c_int32)]
    biblioteca.gr_bellman_ford_todos.argtypes = csr + [matriz(np.float64),
                                                       ctypes.POINTER(ctypes.c_int32), ctypes.c_int]
    biblioteca.gr_johnson.argtypes = csr + [vetor(np.float64), matriz(np.float64),
                                            matriz(np.int32), ctypes.c_int]
    for nome in ("gr_floyd_warshall_classico", "gr_floyd_warshall_blocado", "gr_bellman_ford",
                 "gr_bellman_ford_todos", "gr_johnson"):
        getattr(biblioteca, nome).restype = ctypes.c_int
    biblioteca.gr_compilacao.argtypes = []
    biblioteca.gr_compilacao.restype = ctypes.c_char_p
    _biblioteca = biblioteca
    return biblioteca


def compilacao():
    return _carregar().gr_compilacao().decode()


def ler_csr(nome_arquivo, direcionado=False, transposto=False):
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
        arcos = m if direcionado else 2 * m
        inicio = np.empty(n + 2, np.int64)
        adjacentes = np.empty(arcos, np.int32)
        pesos = np.empty(arcos, np.float64)
        if direcionado:
            codigo = biblioteca.gr_montar_csr_direcionado(leitura, int(transposto), inicio,
                                                          adjacentes, pesos)
        else:
            codigo = biblioteca.gr_montar_csr(leitura, inicio, adjacentes, pesos)
        if codigo != 0:
            raise MemoryError("Memória insuficiente para montar o CSR.")
    finally:
        biblioteca.gr_liberar_leitura(leitura)
    return GrafoCSR(n, inicio, adjacentes, pesos, direcionado=direcionado)


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


def _exigir_csr(grafo):
    if not isinstance(grafo, GrafoCSR):
        raise TypeError("O motor C requer um GrafoCSR: use ler_grafo(arquivo, 'csr').")


def _conferir(codigo, nome):
    if codigo == _ERRO_MEMORIA:
        raise MemoryError(f"Memória insuficiente em {nome}.")
    if codigo != 0:
        raise RuntimeError(f"{nome} devolveu o código {codigo}.")


def _csr(grafo):
    return grafo.numero_vertices, grafo.inicio, grafo.adjacentes, grafo.pesos


def floyd_warshall_c(grafo, versao="blocado", threads=0, bloco=256, curto=None):
    from caminhos_p3 import (INF_INTEIRO, NEG_INTEIRO, ResultadoTodosPares, escala_inteira,
                             marcar_ciclos_negativos)

    _exigir_csr(grafo)
    biblioteca = _carregar()
    n = grafo.numero_vertices
    if versao == "classico":
        distancias = np.empty((n + 1, n + 1), np.float64)
        predecessores = np.empty((n + 1, n + 1), np.int32)
        codigo = biblioteca.gr_floyd_warshall_classico(*_csr(grafo), distancias, predecessores,
                                                       int(threads))
        infinito, marcador, escala = np.inf, -np.inf, None
    elif versao == "blocado":
        escala = escala_inteira(grafo.pesos, n)
        if curto is None:
            curto = n <= np.iinfo(np.int16).max
        distancias = np.empty((n + 1, n + 1), np.int32)
        predecessores = np.empty((n + 1, n + 1), np.int16 if curto else np.int32)
        codigo = biblioteca.gr_floyd_warshall_blocado(
            *_csr(grafo), float(escala), distancias,
            predecessores.ctypes.data_as(ctypes.c_void_p), int(curto), int(bloco), int(threads))
        infinito, marcador = INF_INTEIRO, NEG_INTEIRO
    else:
        raise ValueError("Versão deve ser 'classico' ou 'blocado'.")
    _conferir(codigo, "Floyd-Warshall")
    ciclo = marcar_ciclos_negativos(distancias, predecessores, infinito, marcador)
    return ResultadoTodosPares(distancias, predecessores, ciclo, escala)


def bellman_ford_c(grafo, destino, *, transposto=None, verificar_grafo=False):
    from caminhos_p3 import ResultadoBellmanFord, transpor

    grafo.validar_vertice(destino)
    reverso = transpor(grafo) if transposto is None else transposto
    _exigir_csr(reverso)
    n = reverso.numero_vertices
    distancias = np.empty(n + 1, np.float64)
    sucessores = np.empty(n + 1, np.int32)
    ciclo = ctypes.c_int32()
    _conferir(_carregar().gr_bellman_ford(*_csr(reverso), int(destino), distancias, sucessores,
                                          ctypes.byref(ciclo)), "Bellman-Ford")
    resultado = ResultadoBellmanFord(destino, distancias, sucessores, bool(ciclo.value))
    if verificar_grafo:
        resultado.ciclo_no_grafo = resultado.tem_ciclo_negativo or _ciclo_global(reverso)
    return resultado


def _ciclo_global(grafo):
    n = grafo.numero_vertices
    ciclo = ctypes.c_int32()
    _conferir(_carregar().gr_bellman_ford(*_csr(grafo), 0, np.empty(n + 1, np.float64),
                                          np.empty(n + 1, np.int32), ctypes.byref(ciclo)),
              "Bellman-Ford")
    return bool(ciclo.value)


def bellman_ford_todos_pares_c(grafo, *, transposto=None, threads=0):
    from caminhos_p3 import ResultadoTodosPares, transpor

    reverso = transpor(grafo) if transposto is None else transposto
    _exigir_csr(reverso)
    n = reverso.numero_vertices
    por_destino = np.empty((n + 1, n + 1), np.float64)
    ciclo = ctypes.c_int32()
    _conferir(_carregar().gr_bellman_ford_todos(*_csr(reverso), por_destino, ctypes.byref(ciclo),
                                                int(threads)), "Bellman-Ford")
    return ResultadoTodosPares(por_destino.T, None, bool(ciclo.value))


def johnson_c(grafo, threads=0):
    from caminhos_p3 import ResultadoTodosPares

    _exigir_csr(grafo)
    biblioteca = _carregar()
    n = grafo.numero_vertices
    potencial = np.empty(n + 1, np.float64)
    sucessores = np.empty(n + 1, np.int32)
    ciclo = ctypes.c_int32()
    _conferir(biblioteca.gr_bellman_ford(*_csr(grafo), 0, potencial, sucessores,
                                         ctypes.byref(ciclo)), "Bellman-Ford")
    if ciclo.value:
        return ResultadoTodosPares(None, None, True)
    distancias = np.empty((n + 1, n + 1), np.float64)
    predecessores = np.empty((n + 1, n + 1), np.int32)
    _conferir(biblioteca.gr_johnson(*_csr(grafo), potencial, distancias, predecessores,
                                    int(threads)), "Johnson")
    return ResultadoTodosPares(distancias, predecessores, False)
