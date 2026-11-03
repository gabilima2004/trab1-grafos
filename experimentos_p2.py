"""Estudos de caso ponderados. Leitura e escrita ficam fora do cronômetro."""

import argparse
import random
from math import isclose, isinf
from pathlib import Path
from time import perf_counter

from entrada_saida import ler_grafo
from caminhos_minimos import dijkstra, reconstruir_caminho


def formatar_distancia(valor):
    return "infinito" if isinf(valor) else f"{valor:.12g}"


def estudo_grafo(nome, k=100, semente=242, representacao="lista"):
    grafo = ler_grafo(nome, representacao, ponderado=True)
    if k < 1 or k > grafo.numero_vertices:
        raise ValueError(f"k deve estar entre 1 e {grafo.numero_vertices}.")
    grafo.validar_vertice(10)
    for destino in (20, 30, 40, 50, 60):
        grafo.validar_vertice(destino)
    distancias, pais = dijkstra(grafo, 10)
    linhas = [f"### {Path(nome).name}", "", "| origem | destino | distância | caminho mínimo |",
              "|---|---|---|---|"]
    for destino in (20, 30, 40, 50, 60):
        caminho = reconstruir_caminho(pais, 10, destino)
        rota = " → ".join(map(str, caminho)) if caminho else "sem caminho"
        linhas.append(f"| 10 | {destino} | {formatar_distancia(distancias[destino])} | {rota} |")
    origens = random.Random(semente).sample(range(1, grafo.numero_vertices + 1), k)
    tempos = {"vetor": 0.0, "heap": 0.0}
    for indice, origem in enumerate(origens):
        resultados = {}
        # Alterna a ordem para reduzir viés da ordem de execução.
        metodos = ("vetor", "heap") if indice % 2 == 0 else ("heap", "vetor")
        for metodo in metodos:
            inicio = perf_counter()
            resultado = dijkstra(grafo, origem, metodo)
            tempos[metodo] += perf_counter() - inicio
            resultados[metodo] = resultado[0]
        if not all(isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
                   for a, b in zip(resultados["vetor"], resultados["heap"])):
            raise RuntimeError(f"Dijkstra divergiu para a origem {origem}.")
        print(f"{Path(nome).name}: {indice + 1}/{k} origens concluídas", flush=True)
    linhas += ["", f"Representação: {representacao}; semente: {semente}; k: {k}.",
               "Origens: " + ", ".join(map(str, origens)), "",
               "| implementação | tempo total (s) | tempo médio (s) |",
               "|---|---|---|"]
    for metodo in ("vetor", "heap"):
        linhas.append(f"| {metodo} | {tempos[metodo]:.9f} | {tempos[metodo] / k:.9f} |")
    return "\n".join(linhas)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grafos", nargs="+")
    parser.add_argument("--k", type=int, default=100)
    parser.add_argument("--semente", type=int, default=242)
    parser.add_argument("--representacao", choices=("lista", "matriz"), default="lista")
    parser.add_argument("--saida", default="tabelas_p2.md")
    args = parser.parse_args()
    # Grava cada grafo concluído, preservando resultados em execuções longas.
    with open(args.saida, "w", encoding="utf-8") as arquivo:
        arquivo.write("# Estudos de caso — Parte 2\n\n")
        for nome in args.grafos:
            arquivo.write(estudo_grafo(nome, args.k, args.semente, args.representacao) + "\n\n")
            arquivo.flush()


if __name__ == "__main__":
    main()
