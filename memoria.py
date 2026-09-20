"""Medição da memória usada por cada representação do grafo.

A medição roda em um processo separado: medir no mesmo processo
misturaria a memória das duas representações.
"""

import subprocess
import sys


def rss_mb():
    """Memória residente (RSS) do processo atual, em MB."""

    with open("/proc/self/status") as f:
        for linha in f:
            if linha.startswith("VmRSS:"):
                return int(linha.split()[1]) / 1024.0

    return 0.0


def medir_memoria(nome_arquivo, representacao):
    """Memória (MB) gasta para carregar o grafo, medida em outro processo."""

    saida = subprocess.run(
        [sys.executable, __file__, nome_arquivo, representacao],
        capture_output=True,
        text=True,
    )

    if saida.returncode != 0:
        raise RuntimeError(saida.stderr.strip())

    return float(saida.stdout.strip())


if __name__ == "__main__":
    from entrada_saida import ler_grafo

    arquivo = sys.argv[1]
    representacao = sys.argv[2]

    antes = rss_mb()

    grafo = ler_grafo(arquivo, representacao)

    depois = rss_mb()

    assert grafo.numero_vertices > 0

    print(depois - antes)
