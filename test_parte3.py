import gzip
from math import inf
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import caminhos_p3

from busca import BFS, componentes
from caminhos_minimos import dijkstra
from caminhos_p3 import bellman_ford, floyd_warshall, tem_ciclo_negativo_global
from dfs import DFS, componentes_dfs
from entrada_saida import ler_grafo
from grafo import Grafo
from grafo_csr import montar_csr


class TestParte3(unittest.TestCase):
    def test_leitura_e_buscas_respeitam_sentido(self):
        with TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "grafo.txt.gz"
            with gzip.open(arquivo, "wt") as saida:
                saida.write("4\n1 2 5\n1 2 2\n2 3 0\n")
            for representacao in ("lista", "matriz", "csr"):
                with self.subTest(representacao=representacao):
                    grafo = ler_grafo(arquivo, representacao, direcionado=True)
                    for busca in (BFS, DFS):
                        self.assertEqual(busca(grafo, 1)[1], {1: 0, 2: 1, 3: 2})
                        self.assertEqual(busca(grafo, 3)[1], {3: 0})
                    for fila in ("vetor", "heap"):
                        self.assertEqual(dijkstra(grafo, 1, fila)[0][1:], [0, 2, 2, inf])
                        self.assertEqual(dijkstra(grafo, 3, fila)[0][1:], [inf, inf, 0, inf])
                    self.assertEqual(bellman_ford(grafo, 3).caminho(1), [1, 2, 3])
                    self.assertEqual(floyd_warshall(grafo).caminho(1, 3), [1, 2, 3])
                    comum = ler_grafo(arquivo, representacao)
                    self.assertEqual(dijkstra(comum, 3)[0][1], 2)
                    self.assertEqual(bellman_ford(comum, 1).caminho(3), [3, 2, 1])
                    self.assertEqual(floyd_warshall(comum).caminho(3, 1), [3, 2, 1])

    def conferir_pares(self, grafo, fw):
        for destino in range(1, grafo.numero_vertices + 1):
            bf = bellman_ford(grafo, destino)
            for origem in range(1, grafo.numero_vertices + 1):
                self.assertEqual(bf.distancias[origem], fw.distancias[origem, destino])

    def test_pesos_negativos_caminhos_e_consistencia(self):
        grafo = Grafo(6, ponderado=True, direcionado=True)
        for u, v, peso in ((1, 2, 7), (1, 3, 2), (3, 2, -4),
                           (2, 4, 3), (3, 4, 5), (4, 5, 0)):
            grafo.adicionar_aresta(u, v, peso)
        with self.assertRaises(ValueError):
            dijkstra(grafo, 1)
        fw = floyd_warshall(grafo)
        self.assertFalse(fw.tem_ciclo_negativo)
        self.conferir_pares(grafo, fw)
        self.assertEqual(fw.distancias[1, 5], 1)
        rota = [1, 3, 2, 4, 5]
        self.assertEqual(fw.caminho(1, 5), rota)
        self.assertEqual(bellman_ford(grafo, 5).caminho(1), rota)
        self.assertEqual(fw.caminho(5, 5), [5])
        self.assertEqual(fw.caminho(6, 5), [])
        self.assertEqual(bellman_ford(grafo, 5).caminho(6), [])

    def test_ciclo_negativo_e_alcance(self):
        grafo = Grafo(8, ponderado=True, direcionado=True)
        for u, v, peso in ((1, 2, 4), (2, 3, 1), (3, 2, -2), (3, 4, 1),
                           (5, 4, 2), (6, 6, -1), (7, 8, 2), (8, 7, 2)):
            grafo.adicionar_aresta(u, v, peso)
        fw = floyd_warshall(grafo)
        self.assertTrue(fw.tem_ciclo_negativo)
        bf = bellman_ford(grafo, 4)
        self.assertTrue(bf.tem_ciclo_negativo)
        self.assertEqual(bf.distancias[1:], [-inf, -inf, -inf, 0, 2, inf, inf, inf])
        self.assertEqual(bf.caminho(1), [])
        self.assertEqual(bf.caminho(5), [5, 4])
        self.assertFalse(bellman_ford(grafo, 8).tem_ciclo_negativo)
        self.assertTrue(bellman_ford(grafo, 6).tem_ciclo_negativo)
        self.conferir_pares(grafo, fw)
        self.assertEqual(fw.caminho(1, 4), [])

    def test_ciclo_certificado_antes_da_ultima_rodada(self):
        arestas = [(1, 2, -4), (2, 1, 1), (2, 25, 1)]
        arestas.extend((u, u + 1, 1) for u in range(3, 25))
        grafo = montar_csr(25, *zip(*arestas), direcionado=True)
        bf = bellman_ford(grafo, 25)
        self.assertTrue(bf.tem_ciclo_negativo)
        self.assertEqual(bf.distancias[1], -inf)
        self.assertEqual(bf.distancias[3], 22)
        self.assertEqual(bf.caminho(3), list(range(3, 26)))
        self.conferir_pares(grafo, floyd_warshall(grafo))

    def test_componentes_rejeita_direcionado_apenas(self):
        for direcionado in (False, True):
            grafo = Grafo(2, direcionado=direcionado)
            grafo.adicionar_aresta(2, 1)
            for funcao in (componentes, componentes_dfs):
                if direcionado:
                    with self.assertRaisesRegex(ValueError, "nao direcionado"):
                        funcao(grafo)
                else:
                    self.assertEqual(funcao(grafo)[:2], (1, [2]))

    def test_ciclo_global_inclui_regiao_desconectada(self):
        for tipo in ("lista", "matriz", "csr"):
            for peso_de_volta in (1, 2):
                arestas = [(1, 2, 4), (3, 4, -2), (4, 3, peso_de_volta)]
                if tipo == "csr":
                    grafo = montar_csr(4, *zip(*arestas), direcionado=True)
                else:
                    grafo = Grafo(4, tipo, ponderado=True, direcionado=True)
                    for aresta in arestas:
                        grafo.adicionar_aresta(*aresta)
                self.assertFalse(bellman_ford(grafo, 2).tem_ciclo_negativo)
                self.assertEqual(tem_ciclo_negativo_global(grafo), peso_de_volta == 1)
                self.assertEqual(tem_ciclo_negativo_global(grafo),
                                 floyd_warshall(grafo).tem_ciclo_negativo)

    def test_inspecao_antecipada_com_ciclos_multiplos_e_empates(self):
        arestas = [(1, 2, -4), (1, 2, 8), (2, 1, 1),
                   (2, 40, 1), (2, 40, 1), (3, 4, -3), (4, 3, 1),
                   (4, 40, 2), (5, 6, -2), (6, 5, 1),
                   (7, 1, 2), (8, 3, 4), (9, 40, 3)]
        arestas.extend((u, u + 1, 1) for u in range(10, 40))
        for tipo in ("lista", "csr"):
            if tipo == "csr":
                grafo = montar_csr(40, *zip(*arestas), direcionado=True)
            else:
                grafo = Grafo(40, ponderado=True, direcionado=True)
                for aresta in arestas:
                    grafo.adicionar_aresta(*aresta)
            certificados = []
            inspecionar = caminhos_p3._ciclos_negativos

            def registrar(sucessores, pesos):
                sementes = inspecionar(sucessores, pesos)
                certificados.extend(sementes)
                return sementes

            with patch.object(caminhos_p3, "_ciclos_negativos", registrar):
                bf = bellman_ford(grafo, 40)
            with patch.object(caminhos_p3, "_ciclos_negativos", return_value=[]):
                sem_atalho = bellman_ford(grafo, 40)
            self.assertEqual(set(certificados), {1, 2, 3, 4})
            self.assertEqual(list(bf.distancias), list(sem_atalho.distancias))
            self.assertEqual(list(bf.distancias[1:10]),
                             [-inf, -inf, -inf, -inf, inf, inf, -inf, -inf, 3])
            self.assertEqual(bf.caminho(10), list(range(10, 41)))
            self.assertEqual(list(bf.distancias), list(floyd_warshall(grafo).distancias[:, 40]))

    def test_aresta_negativa_nao_direcionada(self):
        grafo = Grafo(3, ponderado=True)
        grafo.adicionar_aresta(1, 2, -1)
        bf = bellman_ford(grafo, 2)
        self.assertEqual(bf.distancias[1:], [-inf, -inf, inf])
        self.assertTrue(floyd_warshall(grafo).tem_ciclo_negativo)


if __name__ == "__main__":
    unittest.main()
