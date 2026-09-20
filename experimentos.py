"""Estudos de caso do Trabalho - Parte 1.

Roda os 7 experimentos pedidos no enunciado sobre um grafo e escreve o
resultado em um arquivo texto (e na tela).

Uso:
    python3 experimentos.py grafo_1.txt.gz
    python3 experimentos.py grafo_3.txt.gz --sem-matriz --sem-diametro-exato

Experimentos inviáveis no grafo dado (matriz que não cabe na memória,
diâmetro exato caro demais) são pulados com o motivo registrado. As
medições de tempo cobrem apenas o algoritmo de busca.
"""

import argparse
import random
import time

from entrada_saida import ler_grafo
from busca import BFS, componentes
from estatisticas import num_arestas
from dfs import DFS
from distancias import (
    INFINITO,
    distancia,
    diametro,
    diametro_aproximado,
)
from memoria import medir_memoria

REPRESENTACOES = ("lista", "matriz")

# Acima disso a matriz (n^2 bytes) não cabe na memória.
LIMITE_MATRIZ = 50000

# Tempo estimado (s) a partir do qual o diâmetro exato é pulado.
LIMITE_DIAMETRO = 900


def memoria_matriz_gb(numero_vertices):
    """Tamanho da matriz de adjacência em GB (1 byte por posição)."""

    return (numero_vertices + 1) ** 2 / (1024 ** 3)


def tempo_medio_busca(grafo, busca, vertices, rotulo=""):
    """Tempo médio (em segundos) de uma busca, repetida a partir de
    cada vértice da lista. Só o algoritmo entra na conta."""

    total = 0.0

    for i, v in enumerate(vertices, start=1):
        inicio = time.perf_counter()

        busca(grafo, v)

        total += time.perf_counter() - inicio

        if rotulo and (i % 10 == 0 or i == len(vertices)):
            print(f"    {rotulo}: {i}/{len(vertices)} buscas"
                  f" (média {total / i:.4f} s)")

    return total / len(vertices)


def sortear_vertices(numero_vertices, quantidade, semente=42):
    """Vértices iniciais distintos das buscas. A semente fixa faz as
    duas representações serem comparadas com as mesmas buscas."""

    quantidade = min(quantidade, numero_vertices)

    return random.Random(semente).sample(
        range(1, numero_vertices + 1), quantidade
    )


def formatar_distancia(d):
    return "infinito (componentes diferentes)" if d == INFINITO else str(d)


def executar(arquivo, num_buscas, num_buscas_matriz,
             usar_matriz, fazer_diametro_exato, saida):
    linhas = []

    def escrever(texto=""):
        print(texto)
        linhas.append(texto)

    escrever(f"===== Estudos de caso - {arquivo} =====")

    inicio_leitura = time.perf_counter()

    grafo = ler_grafo(arquivo, "lista")

    n = grafo.numero_vertices

    escrever(f"\nNúmero de vértices: {n}")
    escrever(f"Número de arestas: {num_arestas(grafo)}")
    escrever(f"(leitura do arquivo: {time.perf_counter() - inicio_leitura:.1f} s,"
             " fora das medições)")

    if usar_matriz and n > LIMITE_MATRIZ:
        escrever(f"\n[aviso] Matriz de adjacência exigiria"
                 f" {memoria_matriz_gb(n):.1f} GB para n = {n}."
                 " Os experimentos com matriz foram pulados.")
        usar_matriz = False

    representacoes = REPRESENTACOES if usar_matriz else ("lista",)

    # 1. Memória de cada representação
    escrever("\n--- 1. Memória por representação ---")

    memoria = {}

    for rep in representacoes:
        memoria[rep] = medir_memoria(arquivo, rep)
        escrever(f"{rep:7s}: {memoria[rep]:8.2f} MB")

    if usar_matriz:
        if memoria["lista"] > 0:
            escrever("matriz / lista: "
                     f"{memoria['matriz'] / memoria['lista']:.1f}x")
    else:
        escrever(f"matriz : não medida - precisaria de"
                 f" {memoria_matriz_gb(n):.1f} GB (n^2 bytes)")

    # 2 e 3. Tempo médio de BFS e DFS nas duas representações
    escrever("\n--- 2 e 3. Tempo médio de busca ---")

    tempos = {}

    for rep in representacoes:
        # Mesmos vértices iniciais nas duas representações.
        quantidade = num_buscas if rep == "lista" else num_buscas_matriz

        vertices = sortear_vertices(n, num_buscas)[:quantidade]

        g = grafo if rep == "lista" else ler_grafo(arquivo, "matriz")

        for nome, busca in (("BFS", BFS), ("DFS", DFS)):
            tempos[(rep, nome)] = tempo_medio_busca(
                g, busca, vertices, rotulo=f"{nome} - {rep}"
            )

            escrever(f"{nome} - {rep:7s}: {tempos[(rep, nome)]:.6f} s por busca"
                     f"  ({len(vertices)} buscas)")

        if rep == "matriz":
            del g

    if usar_matriz:
        for nome in ("BFS", "DFS"):
            if tempos[("lista", nome)] > 0:
                razao = tempos[("matriz", nome)] / tempos[("lista", nome)]
                escrever(f"{nome}: matriz é {razao:.1f}x o tempo da lista")

    # 4. Pais dos vértices 10, 20 e 30
    escrever("\n--- 4. Pai dos vértices 10, 20 e 30 nas árvores de busca ---")
    escrever("(pai 0 = é a própria raiz; '-' = não alcançado a partir da raiz)")

    alvos = [10, 20, 30]

    for nome, busca in (("BFS", BFS), ("DFS", DFS)):
        for raiz in (1, 2, 3):
            if raiz > n:
                continue

            pai, nivel = busca(grafo, raiz)

            partes = []

            for alvo in alvos:
                if alvo > n:
                    continue

                if alvo == raiz:
                    partes.append(f"pai({alvo}) = 0")
                elif alvo in pai:
                    partes.append(f"pai({alvo}) = {pai[alvo]}"
                                  f" [nível {nivel[alvo]}]")
                else:
                    partes.append(f"pai({alvo}) = -")

            escrever(f"{nome} a partir de {raiz}: " + ", ".join(partes))

    # 5. Distâncias
    escrever("\n--- 5. Distância entre pares de vértices ---")

    for u, v in ((10, 20), (10, 30), (20, 30)):
        if max(u, v) > n:
            continue

        d = distancia(grafo, u, v)

        escrever(f"distância({u}, {v}) = {formatar_distancia(d)}")

    # 6. Componentes conexas
    escrever("\n--- 6. Componentes conexas ---")

    inicio_componentes = time.perf_counter()

    num_componentes, tamanhos, _ = componentes(grafo)

    escrever(f"Número de componentes conexas: {num_componentes}")
    escrever(f"Maior componente: {tamanhos[0]} vértices")
    escrever(f"Menor componente: {tamanhos[-1]} vértices")
    escrever(f"(tempo: {time.perf_counter() - inicio_componentes:.1f} s)")

    # 7. Diâmetro
    escrever("\n--- 7. Diâmetro ---")

    inicio_aprox = time.perf_counter()
    aprox, par_aprox = diametro_aproximado(grafo)
    tempo_aprox = time.perf_counter() - inicio_aprox

    escrever(f"Diâmetro aproximado (varredura dupla): {aprox}"
             f"  [par {par_aprox[0]} - {par_aprox[1]}]"
             f"  em {tempo_aprox:.3f} s")

    estimativa = tempos[("lista", "BFS")] * n

    if fazer_diametro_exato and estimativa > LIMITE_DIAMETRO:
        escrever(f"Diâmetro exato: pulado - levaria cerca de"
                 f" {estimativa / 60:.0f} min ({n} BFS de"
                 f" {tempos[('lista', 'BFS')]:.3f} s)."
                 " Use --forcar-diametro-exato para rodar mesmo assim.")
        fazer_diametro_exato = False

    if fazer_diametro_exato:
        inicio_exato = time.perf_counter()
        exato, par_exato = diametro(grafo, mostrar_progresso=True)
        tempo_exato = time.perf_counter() - inicio_exato

        escrever(f"Diâmetro exato: {exato}"
                 f"  [par {par_exato[0]} - {par_exato[1]}]"
                 f"  em {tempo_exato:.3f} s")
    elif estimativa <= LIMITE_DIAMETRO:
        escrever("Diâmetro exato: não calculado (--sem-diametro-exato)")

    with open(saida, "w") as f:
        f.write("\n".join(linhas) + "\n")

    print(f"\nResultados salvos em {saida}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("arquivo", help="arquivo do grafo (.txt ou .txt.gz)")
    parser.add_argument("--buscas", type=int, default=100,
                        help="quantidade de buscas na lista de adjacência")
    parser.add_argument("--buscas-matriz", type=int, default=None,
                        help="quantidade de buscas na matriz"
                             " (padrão: igual a --buscas)")
    parser.add_argument("--sem-matriz", action="store_true",
                        help="pula os experimentos com matriz de adjacência")
    parser.add_argument("--sem-diametro-exato", action="store_true",
                        help="pula o diâmetro exato")
    parser.add_argument("--forcar-diametro-exato", action="store_true",
                        help="calcula o diâmetro exato mesmo que a"
                             " estimativa de tempo seja alta")
    parser.add_argument("--saida", default=None,
                        help="arquivo de saída dos resultados")

    args = parser.parse_args()

    if args.forcar_diametro_exato:
        global LIMITE_DIAMETRO
        LIMITE_DIAMETRO = float("inf")

    saida = args.saida

    if saida is None:
        base = args.arquivo.split("/")[-1]
        base = base.replace(".txt.gz", "").replace(".txt", "")
        saida = f"resultados_{base}.txt"

    executar(
        args.arquivo,
        args.buscas,
        args.buscas_matriz if args.buscas_matriz is not None else args.buscas,
        not args.sem_matriz,
        not args.sem_diametro_exato,
        saida,
    )


if __name__ == "__main__":
    main()
