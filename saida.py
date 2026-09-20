"""Escrita das árvores de busca (BFS/DFS) em arquivo texto."""


def salvar_arvore(nome_arquivo, raiz, pai, nivel, tipo="BFS"):
    """Grava a árvore gerada pela busca.

    Uma linha por vértice alcançado, no formato:
        vertice pai nivel
    A raiz tem pai 0 e nível 0. Vértices não alcançados a partir da
    raiz não aparecem no arquivo (estão em outra componente conexa).
    """

    vertices = sorted(nivel.keys())

    with open(nome_arquivo, "w") as f:
        f.write(f"# Arvore da {tipo} - raiz {raiz}\n")
        f.write(f"# vertices alcancados: {len(vertices)}\n")
        f.write("# vertice pai nivel\n")

        for v in vertices:
            f.write(f"{v} {pai.get(v, 0)} {nivel[v]}\n")

    return len(vertices)
