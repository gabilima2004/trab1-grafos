import gzip
from math import inf, isclose
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

import motor_c
from caminhos_minimos import dijkstra
from caminhos_p3 import (INF_INTEIRO, NEG_INTEIRO, ResultadoTodosPares, bellman_ford,
                         escala_inteira, floyd_warshall, floyd_warshall_blocado, johnson,
                         tem_ciclo_negativo_global)
from grafo import Grafo
from grafo_csr import ler_grafo_csr, montar_csr

PASTA = Path(__file__).resolve().parent
COM_C = motor_c.disponivel()


def aleatorio(gerador, n, m, negativos=0.0, zeros=0.0):
    origens = gerador.integers(1, n + 1, m)
    destinos = gerador.integers(1, n + 1, m)
    pesos = np.round(gerador.uniform(0, 10, m), 2)
    sinal = gerador.random(m) < negativos
    pesos[sinal] = np.round(-0.3 * pesos[sinal], 2)
    pesos[gerador.random(m) < zeros] = 0.0
    return montar_csr(n, origens, destinos, pesos, direcionado=True)


def casos(semente=7, quantidade=25):
    gerador = np.random.default_rng(semente)
    for _ in range(quantidade):
        n = int(gerador.integers(2, 70))
        yield aleatorio(gerador, n, int(gerador.integers(1, 5 * n)),
                        negativos=float(gerador.choice([0.0, 0.04, 0.3])),
                        zeros=float(gerador.choice([0.0, 0.3])))


def menores_pesos(grafo):
    menores = {}
    for u in range(1, grafo.numero_vertices + 1):
        for v, peso in grafo.vizinhos_com_pesos(u):
            menores[u, v] = min(peso, menores.get((u, v), inf))
    return menores


class Verificacoes:
    def conferir_arvores(self, grafo, resultado):
        pesos = menores_pesos(grafo)
        n = grafo.numero_vertices
        for origem in range(1, n + 1):
            for destino in range(1, n + 1):
                distancia = resultado.distancia(origem, destino)
                caminho = resultado.caminho(origem, destino)
                if distancia in (inf, -inf):
                    self.assertEqual(caminho, [])
                    continue
                self.assertEqual((caminho[0], caminho[-1]), (origem, destino))
                total = sum(pesos[a, b] for a, b in zip(caminho, caminho[1:]))
                self.assertTrue(isclose(total, distancia, abs_tol=1e-9),
                                (origem, destino, total, distancia))


class TodosParesTest(Verificacoes, unittest.TestCase):

    def test_blocado_python_identico_ao_classico(self):
        for grafo in casos():
            n = grafo.numero_vertices
            classico = floyd_warshall(grafo)
            for bloco in (1, 3, 16, 64):
                with self.subTest(n=n, bloco=bloco):
                    blocado = floyd_warshall_blocado(grafo, bloco)
                    self.assertEqual(blocado.tem_ciclo_negativo, classico.tem_ciclo_negativo)
                    np.testing.assert_array_equal(blocado.distancias, classico.distancias)
                    np.testing.assert_array_equal(blocado.predecessores, classico.predecessores)
                    self.conferir_arvores(grafo, blocado)

    def test_floyd_warshall_detecta_ciclo_fora_do_alcance_e_johnson_recusa(self):
        grafo = Grafo(5, ponderado=True, direcionado=True)
        for u, v, peso in ((1, 2, 1), (3, 4, -2), (4, 3, 1), (4, 5, 2)):
            grafo.adicionar_aresta(u, v, peso)
        fw = floyd_warshall_blocado(grafo, 2)
        self.assertTrue(fw.tem_ciclo_negativo)
        self.assertEqual(fw.distancia(1, 2), 1)
        self.assertEqual(fw.distancia(3, 5), -inf)
        self.assertEqual(fw.distancia(5, 3), inf)
        self.assertTrue(johnson(grafo).tem_ciclo_negativo)
        with self.assertRaisesRegex(ValueError, "Ciclo negativo"):
            johnson(grafo).distancia(1, 2)

    def test_johnson_python_igual_ao_floyd_warshall(self):
        for grafo in casos(11, 12):
            n = grafo.numero_vertices
            fw = floyd_warshall(grafo)
            resultado = johnson(grafo)
            self.assertEqual(resultado.tem_ciclo_negativo, tem_ciclo_negativo_global(grafo))
            self.assertEqual(resultado.tem_ciclo_negativo, fw.tem_ciclo_negativo)
            if not resultado.tem_ciclo_negativo:
                np.testing.assert_allclose(resultado.submatriz(range(1, n + 1)),
                                           fw.submatriz(range(1, n + 1)), atol=1e-9)
                self.conferir_arvores(grafo, resultado)

    def test_bellman_ford_informa_ciclo_no_grafo_separadamente(self):
        grafo = Grafo(5, ponderado=True, direcionado=True)
        for u, v, peso in ((1, 2, 3), (2, 3, 1), (4, 5, -2), (5, 4, 1)):
            grafo.adicionar_aresta(u, v, peso)
        resultado = bellman_ford(grafo, 3, verificar_grafo=True)
        self.assertFalse(resultado.tem_ciclo_negativo)
        self.assertTrue(resultado.ciclo_no_grafo)
        self.assertIsNone(bellman_ford(grafo, 3).ciclo_no_grafo)
        grafo.adicionar_aresta(5, 3, 0)
        resultado = bellman_ford(grafo, 3, verificar_grafo=True)
        self.assertTrue(resultado.tem_ciclo_negativo and resultado.ciclo_no_grafo)

    def test_escala_inteira(self):
        self.assertEqual(escala_inteira([1.0, -3.0], 10), 1)
        self.assertEqual(escala_inteira([1.19, -5.0, 10.0], 25000), 100)
        self.assertEqual(escala_inteira([0.125], 10), 1000)
        with self.assertRaisesRegex(ValueError, "seis casas"):
            escala_inteira([0.1234567], 10)
        with self.assertRaisesRegex(ValueError, "grandes demais"):
            escala_inteira([10.5], 10 ** 8)

    def test_resultado_inteiro_converte_infinitos(self):
        distancias = np.array([[INF_INTEIRO] * 3, [INF_INTEIRO, 0, 125],
                               [INF_INTEIRO, NEG_INTEIRO, INF_INTEIRO]], np.int32)
        predecessores = np.array([[0, 0, 0], [0, 0, 1], [0, 0, 0]], np.int16)
        resultado = ResultadoTodosPares(distancias, predecessores, True, 100)
        self.assertEqual(resultado.distancia(1, 2), 1.25)
        self.assertEqual(resultado.distancia(2, 1), -inf)
        self.assertEqual(resultado.distancia(2, 2), inf)
        self.assertEqual(resultado.submatriz([1, 2]).tolist(), [[0.0, 1.25], [-inf, inf]])
        self.assertEqual(resultado.caminho(1, 2), [1, 2])
        self.assertEqual(resultado.caminho(2, 1), [])


@unittest.skipUnless(COM_C, "motor C não compilado")
class MotorCTodosParesTest(Verificacoes, unittest.TestCase):
    def test_leitor_c_direcionado_igual_ao_numpy(self):
        with TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "g.txt.gz"
            with gzip.open(arquivo, "wt") as saida:
                saida.write("5\n1 2 1.5\n3 1 -2\n1 2 0.25\n5 4 3\n2 3 0\n")
            for transposto in (False, True):
                c = ler_grafo_csr(arquivo, leitor="c", direcionado=True, transposto=transposto)
                py = ler_grafo_csr(arquivo, direcionado=True, transposto=transposto)
                self.assertTrue(c.direcionado)
                self.assertEqual(c.numero_arestas, 5)
                for campo in ("inicio", "adjacentes", "pesos"):
                    np.testing.assert_array_equal(getattr(c, campo), getattr(py, campo))

    def test_dijkstra_c_respeita_sentido(self):
        grafo = montar_csr(4, [1, 2, 4], [2, 3, 1], [1.0, 2.0, 0.5], direcionado=True)
        distancias, pais = motor_c.dijkstra_c(grafo, 1)
        self.assertEqual(distancias[1:].tolist(), [0.0, 1.0, 3.0, inf])
        self.assertEqual(distancias[1:].tolist(), dijkstra(grafo, 1)[0][1:])
        self.assertEqual(motor_c.dijkstra_c(grafo, 3)[0][1:].tolist(), [inf, inf, 0.0, inf])

    def test_floyd_classico_c_identico_ao_python(self):
        for grafo in casos(3):
            for threads in (1, 4):
                py = floyd_warshall(grafo)
                c = motor_c.floyd_warshall_c(grafo, "classico", threads)
                np.testing.assert_array_equal(c.distancias, py.distancias)
                np.testing.assert_array_equal(c.predecessores, py.predecessores)
                self.assertEqual(c.tem_ciclo_negativo, py.tem_ciclo_negativo)

    def test_floyd_blocado_c_igual_ao_classico_com_arvores_validas(self):
        for grafo in casos(5):
            n = grafo.numero_vertices
            classico = floyd_warshall(grafo)
            for bloco, threads, curto in ((1, 1, True), (7, 4, True), (32, 2, False), (256, 0, None)):
                with self.subTest(n=n, bloco=bloco, threads=threads, curto=curto):
                    c = motor_c.floyd_warshall_c(grafo, "blocado", threads, bloco, curto)
                    self.assertEqual(c.escala, 100)
                    self.assertEqual(c.predecessores.dtype, np.int32 if curto is False else np.int16)
                    self.assertEqual(c.tem_ciclo_negativo, classico.tem_ciclo_negativo)
                    np.testing.assert_allclose(c.submatriz(range(1, n + 1)),
                                               classico.submatriz(range(1, n + 1)), atol=1e-9)
                    self.conferir_arvores(grafo, c)

    def test_saturacao_evita_estouro_com_ciclo_negativo(self):
        gerador = np.random.default_rng(1)
        n = 120
        origens = list(range(1, n + 1)) + list(gerador.integers(1, n + 1, 6 * n))
        destinos = [u % n + 1 for u in range(1, n + 1)] + list(gerador.integers(1, n + 1, 6 * n))
        pesos = [-99.99] * n + list(np.round(gerador.uniform(0, 1, 6 * n), 2))
        grafo = montar_csr(n, origens, destinos, pesos, direcionado=True)
        for bloco in (1, 16, 256):
            c = motor_c.floyd_warshall_c(grafo, "blocado", 0, bloco)
            self.assertTrue(c.tem_ciclo_negativo)
            self.assertTrue((c.distancias[1:, 1:] == NEG_INTEIRO).all())
        self.assertTrue(np.isneginf(floyd_warshall(grafo).distancias[1:, 1:]).all())

    def test_bellman_ford_c_igual_ao_python(self):
        for grafo in casos(9):
            n = grafo.numero_vertices
            for destino in range(1, n + 1, max(1, n // 5)):
                with self.subTest(n=n, destino=destino):
                    py = bellman_ford(grafo, destino, verificar_grafo=True)
                    c = motor_c.bellman_ford_c(grafo, destino, verificar_grafo=True)
                    self.assertEqual(c.tem_ciclo_negativo, py.tem_ciclo_negativo)
                    self.assertEqual(c.ciclo_no_grafo, py.ciclo_no_grafo)
                    np.testing.assert_allclose(c.distancias[1:], np.asarray(py.distancias)[1:],
                                               atol=1e-9)
                    pesos = menores_pesos(grafo)
                    for origem in range(1, n + 1):
                        caminho = c.caminho(origem)
                        if c.distancias[origem] in (inf, -inf):
                            self.assertEqual(caminho, [])
                            continue
                        self.assertEqual((caminho[0], caminho[-1]), (origem, destino))
                        total = sum(pesos[a, b] for a, b in zip(caminho, caminho[1:]))
                        self.assertTrue(isclose(total, c.distancias[origem], abs_tol=1e-9))

    def test_bellman_ford_todos_pares_c_igual_ao_floyd_warshall(self):
        for grafo in casos(13):
            n = grafo.numero_vertices
            fw = floyd_warshall(grafo)
            c = motor_c.bellman_ford_todos_pares_c(grafo, threads=3)
            np.testing.assert_allclose(c.submatriz(range(1, n + 1)),
                                       fw.submatriz(range(1, n + 1)), atol=1e-9)

    def test_johnson_c_igual_ao_python(self):
        for grafo in casos(17, 15):
            n = grafo.numero_vertices
            py = johnson(grafo)
            c = motor_c.johnson_c(grafo, threads=2)
            self.assertEqual(c.tem_ciclo_negativo, py.tem_ciclo_negativo)
            if not c.tem_ciclo_negativo:
                np.testing.assert_allclose(c.submatriz(range(1, n + 1)),
                                           py.submatriz(range(1, n + 1)), atol=1e-9)
                self.conferir_arvores(grafo, c)

    @unittest.skipUnless((PASTA / "grafo_W_2.txt.gz").exists(), "grafo_W_2.txt.gz ausente")
    def test_valores_oficiais_do_grafo_w2(self):
        arquivo = PASTA / "grafo_W_2.txt.gz"
        original = ler_grafo_csr(arquivo, leitor="c", direcionado=True)
        reverso = ler_grafo_csr(arquivo, leitor="c", direcionado=True, transposto=True)
        self.assertEqual((original.numero_vertices, original.numero_arestas), (25000, 824964))
        esperado = [10.47, 8.48, 8.71]
        for resultado in (motor_c.bellman_ford_c(original, 100, transposto=reverso),
                          bellman_ford(original, 100, transposto=reverso)):
            self.assertFalse(resultado.tem_ciclo_negativo)
            np.testing.assert_allclose([resultado.distancias[u] for u in (10, 20, 30)], esperado)


if __name__ == "__main__":
    unittest.main()
