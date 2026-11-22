"""Calcula as 25 distancias oficiais sem alocar uma matriz V por V."""
import argparse
import csv
from math import fsum, inf, isclose
from pathlib import Path

from busca import BFS
from caminhos_minimos import dijkstra
from caminhos_p3 import bellman_ford
from experimentos_p3 import VERTICES
from grafo_csr import ler_grafo_csr


def verificar_ciclo(reverso, ciclo):
    if len(ciclo) < 2 or ciclo[0] != ciclo[-1]:
        raise ValueError("Informe um ciclo fechado no sentido original.")
    pesos = []
    for u, v in zip(ciclo, ciclo[1:]):
        peso = min((w for x, w in reverso.vizinhos_com_pesos(v) if x == u), default=inf)
        if peso == inf:
            raise ValueError(f"Arco ausente no ciclo: {u} -> {v}")
        pesos.append(peso)
    if fsum(pesos) >= 0:
        raise ValueError("O ciclo informado precisa ter peso negativo.")
    origens = BFS(reverso, ciclo[0])[1]
    return {(u, v) for v in VERTICES if ciclo[0] in BFS(reverso, v)[1]
            for u in VERTICES if u in origens}


def calcular(arquivo, motor, ciclo):
    reverso = ler_grafo_csr(arquivo, direcionado=True, transposto=True)
    for vertice in VERTICES:
        reverso.validar_vertice(vertice)
    certificados = verificar_ciclo(reverso, ciclo) if ciclo else set()
    if motor == "c":
        from motor_c import dijkstra_c
        verificar = dijkstra_c
    else:
        verificar = dijkstra
    linhas = {}
    for destino in VERTICES:
        resultado = bellman_ford(reverso, destino, transposto=reverso)
        referencia = None if reverso.tem_peso_negativo else verificar(reverso, destino)[0]
        for origem in VERTICES:
            valor = float(resultado.distancias[origem])
            validacao = "nenhuma"
            if referencia is not None:
                if not isclose(valor, float(referencia[origem]), rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError(f"Divergencia em {origem} -> {destino}")
                validacao = f"dijkstra_{motor}"
            elif (origem, destino) in certificados:
                if valor != -inf:
                    raise ValueError(f"Ciclo certificado sem -inf em {origem} -> {destino}")
                validacao = "ciclo_negativo_e_alcance"
            linhas[origem, destino] = (valor, validacao)
        del resultado, referencia
        print(f"{arquivo.name}: destino {destino} concluido", flush=True)
    return linhas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grafo", type=Path)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--validar-dijkstra", choices=("python", "c"), default="python")
    parser.add_argument("--ciclo", nargs="+", type=int)
    args = parser.parse_args()
    validacao = args.saida.with_suffix(".validacao.csv")
    for saida in (args.saida, validacao):
        if saida.exists():
            parser.error(f"A saida ja existe: {saida}")
    linhas = calcular(args.grafo, args.validar_dijkstra, args.ciclo)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    with args.saida.open("x", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(("origem", *VERTICES))
        for u in VERTICES:
            escritor.writerow((u, *(linhas[u, v][0] for v in VERTICES)))
    with validacao.open("x", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(("origem", "destino", "algoritmo", "validacao"))
        escritor.writerows((u, v, "bellman_ford", metodo)
                          for (u, v), (_, metodo) in sorted(linhas.items()))


if __name__ == "__main__":
    main()
