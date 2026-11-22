"""Reproduz os estudos da Parte 3 com os arquivos oficiais."""
import argparse
import csv
from contextlib import ExitStack
import json
import platform
from pathlib import Path
from statistics import mean
from time import perf_counter

import numpy as np

from caminhos_p3 import bellman_ford, floyd_warshall, transpor
from entrada_saida import ler_cabecalho
from grafo_csr import ler_grafo_csr

VERTICES = (10, 20, 30, 40, 50)
NOMES = ("bellman_ford", "floyd_warshall", "bellman_ford_todos_pares")


def medir(algoritmo, rodadas, extrair=lambda _: None):
    tempos = []
    dados = None
    for rodada in range(rodadas):
        inicio = perf_counter()
        resultado = algoritmo()
        tempos.append(perf_counter() - inicio)
        if rodada == 0:
            dados = extrair(resultado)
        del resultado
    return tempos, dados


def todos_pares_bellman_ford(grafo, transposto, *, fluxo=False):
    n = grafo.numero_vertices
    if fluxo:
        amostra = [v for v in VERTICES if v <= n]
        colunas = {v: i for i, v in enumerate(amostra)}
        pequena = np.empty((len(amostra), len(amostra)), dtype=np.float64)
        for destino in range(1, n + 1):
            resultado = bellman_ford(grafo, destino, transposto=transposto)
            if destino in colunas:
                pequena[:, colunas[destino]] = np.asarray(resultado.distancias)[amostra]
            del resultado
        return pequena
    distancias = np.empty((n + 1, n + 1), dtype=np.float64, order="F")
    distancias[:, 0] = np.inf
    for destino in range(1, n + 1):
        resultado = bellman_ford(grafo, destino, transposto=transposto)
        distancias[:, destino] = resultado.distancias
        del resultado
    return distancias


def matriz_amostral(distancias):
    return distancias[np.ix_(VERTICES, VERTICES)]


def executar(arquivo, rodadas, limite, tempos, medias, distancias, matrizes):
    n, _ = ler_cabecalho(arquivo)
    nome = arquivo.name
    print(f"{nome}: {n} vertices", flush=True)
    grafo = ler_grafo_csr(arquivo, direcionado=True, transposto=True)

    def registrar(algoritmo, amostras):
        tempos.writerows((nome, algoritmo, i, valor)
                         for i, valor in enumerate(amostras, 1))
        medias.writerow((nome, n, grafo.numero_arestas, algoritmo,
                         len(amostras), mean(amostras), "concluido"))

    amostras, dados = medir(
        lambda: bellman_ford(grafo, 100, transposto=grafo), rodadas,
        lambda r: [(u, r.distancias[u]) for u in (10, 20, 30)])
    registrar(NOMES[0], amostras)
    distancias.writerows((nome, u, 100, valor) for u, valor in dados)

    if n > limite:
        for algoritmo in NOMES[1:]:
            medias.writerow((nome, n, grafo.numero_arestas, algoritmo, 0, "",
                             f"omitido: {n} vertices excedem o limite {limite}"))
        return

    original = transpor(grafo)
    amostras, dados = medir(lambda: floyd_warshall(original), rodadas,
                            lambda r: matriz_amostral(r.distancias))
    registrar(NOMES[1], amostras)
    matrizes.writerows((nome, origem, *linha) for origem, linha in zip(VERTICES, dados))
    amostras, verificacao = medir(lambda: todos_pares_bellman_ford(original, grafo),
                                 rodadas, matriz_amostral)
    registrar(NOMES[2], amostras)
    np.testing.assert_allclose(dados, verificacao)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grafos", nargs="+", type=Path)
    parser.add_argument("--saida", type=Path, default=Path("resultados_p3"))
    parser.add_argument("--rodadas", type=int, default=10)
    parser.add_argument("--limite-todos-pares", type=int, default=2000)
    args = parser.parse_args()
    if args.rodadas < 1 or args.limite_todos_pares < 0:
        parser.error("Use rodadas positivas e limite nao negativo.")
    if args.limite_todos_pares > 2000:
        parser.error("Para todos os pares acima de 2000 vertices, use benchmark_p3.py.")
    args.saida.mkdir(parents=True, exist_ok=True)
    metadados = dict(python=platform.python_version(), numpy=np.__version__,
                     sistema=platform.platform(), rodadas=args.rodadas,
                     limite_todos_pares=args.limite_todos_pares,
                     grafos=[p.name for p in args.grafos], direcionado=True)
    (args.saida / "ambiente.json").write_text(
        json.dumps(metadados, indent=2) + "\n", encoding="utf-8")

    with ExitStack() as pilha:
        arquivos = []
        for nome, cabecalho in (
            ("tempos", ("grafo", "algoritmo", "rodada", "segundos")),
            ("medias", ("grafo", "vertices", "arestas", "algoritmo", "rodadas", "media_s", "estado")),
            ("bellman_ford", ("grafo", "origem", "destino", "distancia")),
            ("floyd_warshall", ("grafo", "origem", *VERTICES)),
        ):
            arquivo = pilha.enter_context((args.saida / f"{nome}.csv").open(
                "w", encoding="utf-8", newline=""))
            escritor = csv.writer(arquivo)
            escritor.writerow(cabecalho)
            arquivos.append((arquivo, escritor))
        for grafo in args.grafos:
            executar(grafo, args.rodadas, args.limite_todos_pares,
                     *(escritor for _, escritor in arquivos))
            for arquivo, _ in arquivos:
                arquivo.flush()


if __name__ == "__main__":
    main()
