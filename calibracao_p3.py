"""Calibracao segura do cronometro em grafos sinteticos limitados."""
import argparse
import json
from pathlib import Path
from statistics import mean
from time import perf_counter

import numpy as np

import benchmark_p3 as bench
from caminhos_p3 import floyd_warshall
from experimentos_p3 import todos_pares_bellman_ford
from grafo_csr import montar_csr

FLOYD = "floyd_warshall"
BF = "bellman_ford_todos_pares"
TAMANHOS = (80, 160, 320)
GRAUS = (4, 16)


def medir():
    bench.exigir_memoria(64 * bench.MIB, None, "calibracao pequena")
    rng = np.random.default_rng(242)
    resultados = []
    for n in TAMANHOS:
        for grau in GRAUS:
            u = np.repeat(np.arange(1, n + 1, dtype=np.int32), grau)
            v = rng.integers(1, n + 1, size=u.size, dtype=np.int32)
            v[::grau] = (u[::grau] % n) + 1
            p = rng.integers(1, 101, size=u.size)
            g = montar_csr(n, u, v, p, direcionado=True)
            r = montar_csr(n, v, u, p, direcionado=True)
            for nome in (FLOYD, BF):
                tempos = []
                for _ in range(bench.RODADAS):
                    t = perf_counter()
                    resultado = (floyd_warshall(g) if nome == FLOYD
                                 else todos_pares_bellman_ford(g, r))
                    tempos.append(perf_counter() - t)
                    del resultado
                resultados.append(dict(vertices=n, arcos=int(u.size), algoritmo=nome,
                                       tempos_s=tempos, media_s=mean(tempos)))
                print(n, grau, nome, f"{mean(tempos):.6f} s", flush=True)
    return dict(tipo="medicao_sintetica", semente=242, ambiente=bench.descrever_ambiente(),
                memoria_disponivel_bytes=bench.memoria_disponivel(), medicoes=resultados)


def estimar(calibracao, n, m, algoritmo, rodadas=10):
    """Faixa de cenarios, sem interpretacao de intervalo estatistico."""
    modelo = BF if algoritmo == "bellman_ford" else algoritmo
    casos = [r for r in calibracao["medicoes"]
             if r["algoritmo"] == modelo and r["vertices"] == max(TAMANHOS)]
    estimativas = []
    for r in casos:
        base = r["vertices"]
        if modelo == FLOYD:
            fator = (n / base) ** 3
        else:
            # Mesmo numero de ondas por destino, ajustando trabalho por onda.
            fator = n * (n + m) / (base * (base + r["arcos"]))
            if algoritmo == "bellman_ford":
                fator /= max(n, 1)
        estimativas.append(r["media_s"] * fator * rodadas)
    return min(estimativas), max(estimativas)


def ler(arquivo, conferir_ambiente=True):
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if dados.get("tipo") != "medicao_sintetica":
        raise ValueError("Arquivo de calibracao invalido.")
    if conferir_ambiente and dados["ambiente"] != bench.descrever_ambiente():
        raise ValueError("Calibracao de outro ambiente ou codigo. Rode a calibracao local.")
    for r in dados["medicoes"]:
        if len(r["tempos_s"]) != bench.RODADAS or r["media_s"] != mean(r["tempos_s"]):
            raise ValueError("Calibracao incompleta ou inconsistente.")
    return dados


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    if args.saida.exists():
        parser.error("A saida ja existe. Escolha outro arquivo.")
    dados = medir()
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    with args.saida.open("x", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, allow_nan=False)
        f.write("\n")


if __name__ == "__main__":
    main()
