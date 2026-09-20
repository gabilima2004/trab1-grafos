from entrada_saida import ler_grafo
from estatisticas import (
    num_arestas,
    grau_min,
    grau_max,
    grau_medio,
    mediana
)
from busca import BFS, componentes
from dfs import DFS
from distancias import distancia, diametro, diametro_aproximado, INFINITO
from saida import salvar_arvore


def escolher_representacao():
    print("\nEscolha a representação do grafo:")
    print("1 - Lista de adjacência")
    print("2 - Matriz de adjacência")

    opcao = input("Opção: ").strip()

    if opcao == "1":
        return "lista"

    if opcao == "2":
        return "matriz"

    print("Opção inválida, usando lista de adjacência.")

    return "lista"


def mostrar_estatisticas(grafo):
    print("\n--- Grafo ---")
    print("Número de vértices:", grafo.numero_vertices)
    print("Número de arestas:", num_arestas(grafo))

    print("\n--- Estatísticas ---")
    print("Grau mínimo:", grau_min(grafo))
    print("Grau máximo:", grau_max(grafo))
    print("Grau médio:", grau_medio(grafo))
    print("Mediana:", mediana(grafo))


def executar_busca(grafo, tipo):
    """Roda BFS ou DFS a partir de um vértice dado pelo usuário e grava
    a árvore (pai e nível de cada vértice) em um arquivo."""

    busca = BFS if tipo == "BFS" else DFS

    v_inicial = int(input(f"\nDigite o vértice inicial da {tipo}: "))

    pai, nivel = busca(grafo, v_inicial)

    print(f"\n--- {tipo} ---")
    print("Pai:", pai)
    print("Nível:", nivel)

    nome_arquivo = f"arvore_{tipo.lower()}_{v_inicial}.txt"

    total = salvar_arvore(nome_arquivo, v_inicial, pai, nivel, tipo)

    print(f"Árvore com {total} vértices salva em {nome_arquivo}")


def mostrar_distancia(grafo):
    u = int(input("\nVértice de origem: "))
    v = int(input("Vértice de destino: "))

    d = distancia(grafo, u, v)

    if d == INFINITO:
        print(f"Não existe caminho entre {u} e {v}"
              " (estão em componentes diferentes).")
    else:
        print(f"Distância entre {u} e {v}: {d}")


def mostrar_diametro(grafo):
    print("\n1 - Diâmetro exato (uma BFS por vértice, lento em grafos grandes)")
    print("2 - Diâmetro aproximado (varredura dupla)")

    opcao = input("Opção: ").strip()

    if opcao == "1":
        valor, par = diametro(grafo, mostrar_progresso=True)
        print(f"Diâmetro exato: {valor} (entre os vértices {par[0]} e {par[1]})")
    else:
        valor, par = diametro_aproximado(grafo)
        print(f"Diâmetro aproximado: {valor}"
              f" (entre os vértices {par[0]} e {par[1]})")


def mostrar_componentes(grafo):
    num_componentes, tamanhos, componentes_grafo = componentes(grafo)

    print("\n--- Componentes conexas ---")
    print("Número de componentes:", num_componentes)
    print("Maior componente:", tamanhos[0], "vértices")
    print("Menor componente:", tamanhos[-1], "vértices")

    mostrar_todas = input(
        "Listar os vértices de cada componente? (s/n): "
    ).strip().lower()

    if mostrar_todas != "s":
        return

    for i in range(num_componentes):
        print(
            f"Componente {i + 1}: "
            f"tamanho = {tamanhos[i]}, "
            f"vértices = {componentes_grafo[i]}"
        )


def main():
    nome_arquivo = input("Digite o nome do arquivo do grafo: ").strip()

    representacao = escolher_representacao()

    grafo = ler_grafo(nome_arquivo, representacao)

    mostrar_estatisticas(grafo)

    while True:
        print("\n--- Menu ---")
        print("1 - BFS (árvore com pai e nível)")
        print("2 - DFS (árvore com pai e nível)")
        print("3 - Distância entre dois vértices")
        print("4 - Diâmetro")
        print("5 - Componentes conexas")
        print("6 - Estatísticas do grafo")
        print("0 - Sair")

        opcao = input("Opção: ").strip()

        if opcao == "1":
            executar_busca(grafo, "BFS")
        elif opcao == "2":
            executar_busca(grafo, "DFS")
        elif opcao == "3":
            mostrar_distancia(grafo)
        elif opcao == "4":
            mostrar_diametro(grafo)
        elif opcao == "5":
            mostrar_componentes(grafo)
        elif opcao == "6":
            mostrar_estatisticas(grafo)
        elif opcao == "0":
            break
        else:
            print("Opção inválida.")


if __name__ == "__main__":
    main()
