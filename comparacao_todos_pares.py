import argparse
import gc
import json
import os
import platform
from math import isinf
from pathlib import Path
from time import perf_counter

import numpy as np

import motor_c
from caminhos_p3 import (bellman_ford, floyd_warshall, floyd_warshall_blocado, johnson,
                         transpor)
from experimentos_p3 import todos_pares_bellman_ford
from grafo_csr import ler_grafo_csr, montar_csr

VERTICES = [10, 20, 30, 40, 50]
ORIGENS_BF = [10, 20, 30]
DESTINO_BF = 100


def algoritmos(threads):
    return {
        "bellman_ford_py": ("destino", lambda g, r: bellman_ford(g, DESTINO_BF, transposto=r)),
        "bellman_ford_c": ("destino", lambda g, r: motor_c.bellman_ford_c(g, DESTINO_BF, transposto=r)),
        "fw_classico_py": ("pares", lambda g, r: floyd_warshall(g)),
        "fw_blocado_py": ("pares", lambda g, r: floyd_warshall_blocado(g)),
        "fw_classico_c": ("pares", lambda g, r: motor_c.floyd_warshall_c(g, "classico", threads)),
        "fw_blocado_c": ("pares", lambda g, r: motor_c.floyd_warshall_c(g, "blocado", threads)),
        "fw_blocado_c_1t": ("pares", lambda g, r: motor_c.floyd_warshall_c(g, "blocado", 1)),
        "fw_classico_c_1t": ("pares", lambda g, r: motor_c.floyd_warshall_c(g, "classico", 1)),
        "bf_todos_py": ("matriz", lambda g, r: todos_pares_bellman_ford(g, r)),
        "bf_todos_c": ("pares", lambda g, r: motor_c.bellman_ford_todos_pares_c(g, transposto=r,
                                                                                threads=threads)),
        "johnson_py": ("pares", lambda g, r: johnson(g)),
        "johnson_c": ("pares", lambda g, r: motor_c.johnson_c(g, threads)),
    }


def numero(valor):
    valor = float(valor)
    return str(valor) if isinf(valor) else valor


def extrair(tipo, resultado, vertices):
    if tipo == "destino":
        return {"distancias": {str(u): numero(resultado.distancias[u]) for u in ORIGENS_BF},
                "ciclo_negativo": bool(resultado.tem_ciclo_negativo)}
    if tipo == "matriz":
        return {"amostra": [[numero(x) for x in linha]
                            for linha in resultado[np.ix_(vertices, vertices)]],
                "ciclo_negativo": None}
    amostra = None
    if resultado.distancias is not None:
        amostra = [[numero(x) for x in linha] for linha in resultado.submatriz(vertices)]
    return {"amostra": amostra, "ciclo_negativo": bool(resultado.tem_ciclo_negativo)}


def gravar(caminho, estado):
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporario, caminho)


def ambiente(threads):
    return {"python": platform.python_version(), "numpy": np.__version__,
            "sistema": platform.platform(), "processador": platform.processor(),
            "nucleos": os.cpu_count(), "threads": threads or os.cpu_count(),
            "compilacao_c": motor_c.compilacao()}


def oficiais(args, saida):
    tabela = algoritmos(args.threads)
    planos = dict(item.split("=") for item in args.rodadas)
    for arquivo in args.grafos:
        caminho = saida / f"{arquivo.name}.json"
        estado = (json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists()
                  else {"grafo": arquivo.name, "algoritmos": {}})
        estado["ambiente"] = ambiente(args.threads)
        original = ler_grafo_csr(arquivo, leitor="c", direcionado=True)
        reverso = ler_grafo_csr(arquivo, leitor="c", direcionado=True, transposto=True)
        n = original.numero_vertices
        estado.update(vertices=n, arcos=int(original.numero_arestas))
        for chave, texto in planos.items():
            tipo, executar = tabela[chave]
            if tipo != "destino" and n > args.limite_todos_pares:
                estado["algoritmos"][chave] = {"omitido": f"{n} vertices acima do limite "
                                                          f"{args.limite_todos_pares}"}
                gravar(caminho, estado)
                continue
            medir(estado, chave, tipo, lambda: executar(original, reverso), int(texto),
                  VERTICES, lambda: gravar(caminho, estado))
        del original, reverso
        gc.collect()


def sintetico(n, grau, semente):
    gerador = np.random.default_rng(semente)
    m = n * grau
    origens = gerador.integers(1, n + 1, m)
    destinos = gerador.integers(1, n + 1, m)
    pesos = np.round(gerador.uniform(0, 10, m), 2)
    return montar_csr(n, origens, destinos, pesos, direcionado=True)


def sinteticos(args, saida):
    tabela = algoritmos(args.threads)
    caminho = saida / "sinteticos.json"
    estado = (json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists()
              else {"grafo": "sinteticos", "casos": {}})
    estado["ambiente"] = ambiente(args.threads)
    for n in args.tamanhos:
        original = sintetico(n, args.grau, n)
        reverso = transpor(original)
        amostra = list(range(1, 6))
        caso = estado["casos"].setdefault(str(n), {"vertices": n, "arcos": int(original.numero_arestas),
                                                   "algoritmos": {}})
        visao = {"grafo": f"sintetico_{n}", "algoritmos": caso["algoritmos"]}
        for chave in args.algoritmos_sinteticos:
            tipo, executar = tabela[chave]
            medir(visao, chave, tipo, lambda: executar(original, reverso),
                  args.rodadas_sinteticos, amostra, lambda: gravar(caminho, estado))


def medir(visao, chave, tipo, executar, rodadas, vertices, salvar):
    registro = visao["algoritmos"].setdefault(chave, {"tempos": []})
    registro["rodadas_planejadas"] = rodadas
    while len(registro["tempos"]) < rodadas:
        gc.collect()
        inicio = perf_counter()
        resultado = executar()
        segundos = perf_counter() - inicio
        if "resultado" not in registro:
            registro["resultado"] = extrair(tipo, resultado, vertices)
        del resultado
        registro["tempos"].append(segundos)
        registro["media_s"] = sum(registro["tempos"]) / len(registro["tempos"])
        salvar()
        print(f"{visao['grafo']} {chave}: rodada {len(registro['tempos'])}/{rodadas} "
              f"{segundos:.3f} s", flush=True)


def conferir(saida):
    divergencias = []
    for caminho in sorted(saida.glob("*.json")):
        estado = json.loads(caminho.read_text(encoding="utf-8"))
        casos = estado.get("casos") or {estado["grafo"]: estado}
        for nome, caso in casos.items():
            amostras = {chave: np.array(r["resultado"]["amostra"], dtype=float)
                        for chave, r in caso["algoritmos"].items()
                        if r.get("resultado", {}).get("amostra") is not None}
            if not amostras:
                continue
            referencia_nome, referencia = next(iter(amostras.items()))
            for chave, matriz in amostras.items():
                if not np.allclose(matriz, referencia, atol=1e-9, equal_nan=True):
                    divergencias.append(f"{caminho.name}/{nome}: {chave} difere de {referencia_nome}")
    for linha in divergencias:
        print(linha)
    print("Amostras concordam." if not divergencias else f"{len(divergencias)} divergencias.")
    return not divergencias


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("grafos", nargs="*", type=Path)
    parser.add_argument("--saida", type=Path, default=Path("resultados_p3/todos_pares"))
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--limite-todos-pares", type=int, default=25000)
    parser.add_argument("--rodadas", nargs="*", default=[
        "bellman_ford_py=10", "bellman_ford_c=10", "fw_blocado_c=10", "bf_todos_c=10",
        "johnson_c=10", "fw_classico_c=2"])
    parser.add_argument("--tamanhos", nargs="*", type=int, default=[])
    parser.add_argument("--grau", type=int, default=22)
    parser.add_argument("--rodadas-sinteticos", type=int, default=3)
    parser.add_argument("--algoritmos-sinteticos", nargs="*", default=[
        "fw_classico_py", "fw_blocado_py", "fw_classico_c_1t", "fw_blocado_c_1t",
        "fw_classico_c", "fw_blocado_c", "bf_todos_py", "bf_todos_c", "johnson_py", "johnson_c"])
    parser.add_argument("--conferir", action="store_true")
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    if args.conferir:
        raise SystemExit(0 if conferir(args.saida) else 1)
    if args.tamanhos:
        sinteticos(args, args.saida)
    if args.grafos:
        oficiais(args, args.saida)
    conferir(args.saida)


if __name__ == "__main__":
    main()
