from time import perf_counter

from entrada_saida import ler_cabecalho, ler_grafo
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
from caminhos_minimos import dijkstra, reconstruir_caminho, salvar_caminhos

# Mesmo limite da parte 1 (experimentos.LIMITE_MATRIZ = 50000 vértices):
# cerca de 2,5 GB. A matriz ponderada usa 8 bytes por posição.
LIMITE_MATRIZ_BYTES = 50_001 ** 2


def escolher_representacao():
    print("\nEscolha a representação do grafo:")
    print("1 - Lista de adjacência")
    print("2 - Matriz de adjacência")
    print("3 - CSR compacta (grafos ponderados grandes; requer numpy)")

    opcao = input("Opção: ").strip()

    if opcao == "1":
        return "lista"

    if opcao == "2":
        return "matriz"

    if opcao == "3":
        return "csr"

    print("Opção inválida, usando lista de adjacência.")

    return "lista"


def representacao_viavel(nome_arquivo, representacao):
    """Troca a matriz por outra representação quando ela não cabe na memória."""
    if representacao != "matriz":
        return representacao
    numero_vertices, ponderado = ler_cabecalho(nome_arquivo)
    tamanho = (numero_vertices + 1) ** 2 * (8 if ponderado else 1)
    if tamanho <= LIMITE_MATRIZ_BYTES:
        return representacao
    alternativa = "csr" if ponderado else "lista"
    print(f"A matriz exigiria {tamanho / 1024 ** 3:.1f} GB; usando {alternativa}.")
    return alternativa


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

    grafo.validar_vertice(u)
    grafo.validar_vertice(v)
    if grafo.ponderado:
        distancias, pais = dijkstra(grafo, u)
        print(f"Distância entre {u} e {v}: {distancias[v]}")
        print("Caminho:", reconstruir_caminho(pais, u, v))
        return
    d = distancia(grafo, u, v)

    if d == INFINITO:
        print(f"Não existe caminho entre {u} e {v}"
              " (estão em componentes diferentes).")
    else:
        print(f"Distância entre {u} e {v}: {d}")


def mostrar_diametro(grafo):
    if grafo.ponderado:
        print("O diâmetro da parte 1 usa número de arestas e se aplica a grafos sem pesos.")
        return
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


def escolher_motor(grafo):
    """O motor C (make) roda sobre a representação CSR."""
    if grafo.representacao != "csr":
        return "python"
    from motor_c import disponivel
    if not disponivel():
        print("Motor C não compilado (rode make); usando Python.")
        return "python"
    opcao = input("Motor (1 - Python, 2 - C): ").strip()
    return "c" if opcao == "2" else "python"


def executar_dijkstra(grafo):
    origem = int(input("Vértice de origem: "))
    opcao = input("Implementação (1 - vetor, 2 - heap): ").strip()
    if opcao not in ("1", "2"):
        raise ValueError("Escolha 1 ou 2.")
    metodo = "vetor" if opcao == "1" else "heap"
    motor = escolher_motor(grafo)
    inicio = perf_counter()
    if motor == "c":
        from motor_c import dijkstra_c
        distancias, pais = dijkstra_c(grafo, origem, metodo)
    else:
        distancias, pais = dijkstra(grafo, origem, metodo)
    print(f"Dijkstra ({motor}, {metodo}) em {perf_counter() - inicio:.4f} s")
    nome = f"caminhos_{metodo}_{origem}.txt" if motor == "python" else f"caminhos_c_{metodo}_{origem}.txt"
    salvar_caminhos(nome, origem, distancias, pais)
    print(f"Distâncias e árvore de caminhos mínimos salvas em {nome}")
    texto = input("Destino para consultar o caminho (Enter para voltar): ").strip()
    if texto:
        destino = int(texto)
        grafo.validar_vertice(destino)
        print("Distância:", distancias[destino])
        print("Caminho:", reconstruir_caminho(pais, origem, destino))


def main():
    nome_arquivo = input("Digite o nome do arquivo do grafo: ").strip()

    representacao = representacao_viavel(nome_arquivo, escolher_representacao())

    grafo = ler_grafo(nome_arquivo, representacao)

    while True:
        print("\n--- Menu ---")
        print("1 - BFS (árvore com pai e nível)")
        print("2 - DFS (árvore com pai e nível)")
        print("3 - Distância entre dois vértices")
        print("4 - Diâmetro")
        print("5 - Componentes conexas")
        print("6 - Estatísticas do grafo")
        print("7 - Dijkstra (distâncias e árvore de caminhos mínimos)")
        print("0 - Sair")

        opcao = input("Opção: ").strip()

        try:
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
            elif opcao == "7":
                executar_dijkstra(grafo)
            elif opcao == "0":
                break
            else:
                print("Opção inválida.")
        except ValueError as erro:
            print(f"Erro: {erro}")


if __name__ == "__main__":
    main()
