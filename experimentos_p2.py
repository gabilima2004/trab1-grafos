"""Estudos de caso dos grafos ponderados: caminhos a partir de 10 e tempos.

Compara até quatro configurações de Dijkstra, motor Python ou C e fila vetor
ou heap, sobre as mesmas origens sorteadas. Só a chamada a Dijkstra é
cronometrada; leitura, verificação e escrita ficam fora do cronômetro.

    .venv/bin/python experimentos_p2.py grafo_W_3.txt.gz grafo_W_4.txt.gz --cpu 0

Cada configuração tem um orçamento de tempo por grafo (--limite). Quando nem
uma execução cabe no orçamento, o tempo médio é estimado por uma execução
parcial (--sonda): tempo por vértice extraído da fila × número médio de
vértices alcançados pelas origens. Os resultados de cada grafo ficam em
resultados_p2/<grafo>.json e as tabelas são regeneradas em tabelas_p2.md.
"""

import argparse
import gc
import hashlib
import json
import os
import platform
import random
from array import array
from contextlib import contextmanager
from datetime import datetime
from math import inf, isinf
from pathlib import Path
from time import perf_counter

from caminhos_minimos import FILAS, dijkstra, reconstruir_caminho
from entrada_saida import ler_grafo

ORIGEM_CAMINHOS = 10
DESTINOS = (20, 30, 40, 50, 60)
# As mais rápidas primeiro: a primeira execução de cada origem é a referência
# das demais, e o número de vértices que ela alcança orienta as estimativas.
CONFIGURACOES = (("c", "heap"), ("python", "heap"), ("c", "vetor"), ("python", "vetor"))


def formatar_distancia(valor):
    return "infinito" if isinf(valor) else f"{valor:.12g}"


def nome_configuracao(motor, fila):
    return f"{motor}-{fila}"


@contextmanager
def sem_coleta_de_lixo():
    """Como no timeit: a coleta de lixo não interrompe a medição."""
    ativa = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if ativa:
            gc.enable()


class FilaComPrazo:
    """Fábrica de filas que encerram o Dijkstra num prazo (execução parcial).

    Ao fim do prazo, extrair_minimo devolve None, como uma fila vazia, e o
    laço de caminhos_minimos.dijkstra termina normalmente.
    """

    def __init__(self, classe, segundos):
        self.classe = classe
        self.segundos = segundos
        self.extracoes = 0
        self.interrompida = False

    def __call__(self, distancias):
        fila = self.classe(distancias)
        extrair = fila.extrair_minimo
        prazo = perf_counter() + self.segundos

        def extrair_com_prazo():
            if perf_counter() >= prazo:
                self.interrompida = True
                return None
            vertice = extrair()
            if vertice is not None:
                self.extracoes += 1
            return vertice

        fila.extrair_minimo = extrair_com_prazo
        return fila


def executar(grafo, motor, fila, origem):
    """Uma execução completa e cronometrada.

    Devolve (segundos, segundos medidos dentro do C ou None, (distancias, pais)).
    """
    if motor == "c":
        from motor_c import executar_c
    with sem_coleta_de_lixo():
        inicio = perf_counter()
        if motor == "c":
            execucao = executar_c(grafo, origem, fila)
        else:
            resultado = dijkstra(grafo, origem, fila)
        segundos = perf_counter() - inicio
    if motor == "c":
        return segundos, execucao.segundos, (execucao.distancias, execucao.pais)
    return segundos, None, resultado


def sondar(grafo, motor, fila, origem, segundos):
    """Execução parcial com prazo: devolve (segundos, vértices extraídos, completa)."""
    with sem_coleta_de_lixo():
        if motor == "c":
            from motor_c import executar_c
            execucao = executar_c(grafo, origem, fila, limite_segundos=segundos)
            return execucao.segundos, execucao.extracoes, execucao.segundos < segundos
        fabrica = FilaComPrazo(FILAS[fila], segundos)
        inicio = perf_counter()
        dijkstra(grafo, origem, fabrica)
        return perf_counter() - inicio, fabrica.extracoes, not fabrica.interrompida


def impressao_digital(distancias, pais):
    """Resumo de distâncias e pais, igual nos dois motores quando os vetores
    coincidem bit a bit (o motor Python usa None onde o C usa 0)."""
    resumo = hashlib.blake2b(digest_size=16)
    if isinstance(distancias, list):
        resumo.update(array("d", distancias))
        resumo.update(array("i", [0 if p is None else p for p in pais]))
    else:
        resumo.update(distancias)
        resumo.update(pais)
    return resumo.hexdigest()


def contar_alcancados(distancias):
    if isinstance(distancias, list):
        return len(distancias) - distancias.count(inf)
    import numpy as np
    return int(np.count_nonzero(np.isfinite(distancias)))


def carregar(nome, representacao, leitor):
    if representacao == "csr":
        from grafo_csr import ler_grafo_csr
        return ler_grafo_csr(nome, leitor)
    return ler_grafo(nome, representacao, ponderado=True)


def ambiente():
    info = {"data": datetime.now().isoformat(timespec="seconds"),
            "python": platform.python_version(), "sistema": platform.platform()}
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as arquivo:
            info["processador"] = next(linha.split(":", 1)[1].strip() for linha in arquivo
                                       if linha.startswith("model name"))
        info["nucleos_permitidos"] = sorted(os.sched_getaffinity(0))
    except (OSError, StopIteration, AttributeError):
        pass
    for chave, caminho in (("perfil_de_energia", "/sys/firmware/acpi/platform_profile"),
                           ("tomada", "/sys/class/power_supply/AC/online")):
        try:
            info[chave] = Path(caminho).read_text().strip()
        except OSError:
            pass
    try:
        import numpy
        info["numpy"] = numpy.__version__
        from motor_c import compilacao, disponivel
        if disponivel():
            info["motor_c"] = compilacao()
    except ImportError:
        pass
    return info


def estudo_caminhos(grafo, motores):
    """Uma árvore a partir de 10 em cada motor; os resultados devem coincidir."""
    caminhos, digitais = None, set()
    for motor in motores:
        _, _, (distancias, pais) = executar(grafo, motor, "heap", ORIGEM_CAMINHOS)
        digitais.add(impressao_digital(distancias, pais))
        if caminhos is None:
            caminhos = [{"destino": destino, "distancia": float(distancias[destino]),
                         "caminho": reconstruir_caminho(pais, ORIGEM_CAMINHOS, destino)}
                        for destino in DESTINOS]
        del distancias, pais
    if len(digitais) > 1:
        raise RuntimeError("Os motores divergiram a partir do vértice 10.")
    return caminhos


def decidir_por_sonda(grafo, estado, origem, sonda, alcance, numero_vertices):
    """Executa uma sonda e decide entre medir ou estimar a configuração."""
    orcamento = min(sonda, estado["limite"])
    segundos, extracoes, completa = sondar(grafo, estado["motor"], estado["fila"], origem, orcamento)
    por_extracao = segundos / max(extracoes, 1)
    # Cota conservadora para uma execução: a origem pode estar numa componente
    # pequena, então vale o maior alcance já observado (ou n).
    maior_alcance = max(alcance.values(), default=numero_vertices)
    uma_execucao = segundos if completa and extracoes >= maior_alcance else por_extracao * maior_alcance
    estado["sonda"] = {"origem": origem, "segundos": segundos, "extracoes": extracoes,
                       "completa": completa, "segundos_por_extracao": por_extracao}
    if uma_execucao > estado["limite"]:
        estado["situacao"] = "estimado"
        estado["_ativa"] = False
    estado["_decidida"] = True


def executar_estudo(nome, k=100, semente=242, representacao="lista", motores=("python",),
                    filas=("vetor", "heap"), limite=None, sonda=60.0, leitor="numpy",
                    k_config=None, limite_config=None, avisar=print):
    """Roda os dois estudos de caso em um grafo e devolve um dicionário."""
    configuracoes = [(m, f) for m, f in CONFIGURACOES if m in motores and f in filas]
    if not configuracoes:
        raise ValueError("Nenhuma configuração selecionada.")
    if "c" in motores and representacao != "csr":
        raise ValueError("O motor C requer a representação 'csr'.")
    k_config, limite_config = k_config or {}, limite_config or {}
    titulo = Path(nome).name

    inicio = perf_counter()
    grafo = carregar(nome, representacao, leitor)
    tempo_leitura = perf_counter() - inicio
    n = grafo.numero_vertices
    if k < 1 or k > n:
        raise ValueError(f"k deve estar entre 1 e {n}.")
    for vertice in (ORIGEM_CAMINHOS, *DESTINOS):
        grafo.validar_vertice(vertice)
    avisar(f"{titulo}: {n} vértices lidos em {tempo_leitura:.1f} s", flush=True)

    motores_usados = list(dict.fromkeys(motor for motor, _ in configuracoes))
    caminhos = estudo_caminhos(grafo, motores_usados)

    origens = random.Random(semente).sample(range(1, n + 1), k)
    estados = []
    for motor, fila in configuracoes:
        nome_cfg = nome_configuracao(motor, fila)
        limite_cfg = limite_config.get(nome_cfg, limite)
        estados.append({"motor": motor, "fila": fila, "k_alvo": min(k, k_config.get(nome_cfg, k)),
                        "limite": limite_cfg, "origens": [], "tempos": [], "tempos_c": [],
                        "situacao": "medido", "sonda": None, "estimativa_media": None,
                        "_ativa": True, "_decidida": limite_cfg is None})
    digitais, alcance = {}, {}
    for origem in origens:
        for estado in estados:
            if estado["_ativa"] and not estado["_decidida"]:
                decidir_por_sonda(grafo, estado, origem, sonda, alcance, n)
            if not estado["_ativa"]:
                continue
            segundos, segundos_c, resultado = executar(grafo, estado["motor"], estado["fila"], origem)
            digital = impressao_digital(*resultado)
            alcance.setdefault(origem, contar_alcancados(resultado[0]))
            del resultado
            nome_cfg = nome_configuracao(estado["motor"], estado["fila"])
            if digitais.setdefault(origem, digital) != digital:
                raise RuntimeError(f"{nome_cfg} divergiu das demais configurações na origem {origem}.")
            estado["origens"].append(origem)
            estado["tempos"].append(segundos)
            if segundos_c is not None:
                estado["tempos_c"].append(segundos_c)
            total = sum(estado["tempos"])
            avisar(f"{titulo} [{nome_cfg}] {len(estado['tempos'])}/{estado['k_alvo']} origens: "
                   f"{segundos:.4f} s (total {total:.1f} s)", flush=True)
            if len(estado["tempos"]) >= estado["k_alvo"]:
                estado["_ativa"] = False
            elif estado["limite"] is not None and total >= estado["limite"]:
                estado["_ativa"] = False
                estado["situacao"] = "limite"
        if not any(estado["_ativa"] for estado in estados):
            break

    alcance_medio = sum(alcance.values()) / len(alcance) if alcance else n
    for estado in estados:
        if estado["situacao"] == "estimado":
            estado["estimativa_media"] = estado["sonda"]["segundos_por_extracao"] * alcance_medio
        for chave in ("_ativa", "_decidida"):
            del estado[chave]
    return {"grafo": titulo, "vertices": n, "arestas": getattr(grafo, "numero_arestas", None),
            "representacao": representacao, "leitor": leitor if representacao == "csr" else None,
            "tempo_leitura": tempo_leitura, "semente": semente, "k": k, "origens": origens,
            "alcance_medio": alcance_medio, "limite": limite, "sonda": sonda,
            "caminhos": caminhos, "configuracoes": estados, "ambiente": ambiente()}


def formatar_segundos(valor, estimado=False):
    if valor is None:
        return "-"
    return f"{'≈ ' if estimado else ''}{valor:.4g}"


def media(configuracao):
    if configuracao["tempos"]:
        return sum(configuracao["tempos"]) / len(configuracao["tempos"]), False
    return configuracao["estimativa_media"], True


def markdown_grafo(resultado):
    leitura = f", leitor {resultado['leitor']}" if resultado["leitor"] else ""
    linhas = [f"### {resultado['grafo']}", "",
              f"{resultado['vertices']} vértices; representação {resultado['representacao']}{leitura}; "
              f"leitura em {resultado['tempo_leitura']:.1f} s.", "",
              "| origem | destino | distância | caminho mínimo |", "|---|---|---|---|"]
    for item in resultado["caminhos"]:
        rota = " → ".join(map(str, item["caminho"])) if item["caminho"] else "sem caminho"
        linhas.append(f"| {ORIGEM_CAMINHOS} | {item['destino']} | "
                      f"{formatar_distancia(item['distancia'])} | {rota} |")
    linhas += ["", f"Semente {resultado['semente']}; k = {resultado['k']}; cada configuração usa as "
               f"primeiras origens da mesma lista; em média {resultado['alcance_medio']:.0f} vértices "
               "alcançados por origem.", "",
               "| motor | fila | origens medidas | tempo total (s) | tempo médio (s) | situação |",
               "|---|---|---|---|---|---|"]
    for cfg in resultado["configuracoes"]:
        valor, estimado = media(cfg)
        total = f"{sum(cfg['tempos']):.4g}" if cfg["tempos"] else "-"
        if cfg["situacao"] == "estimado":
            sonda = cfg["sonda"]
            situacao = (f"estimado: {sonda['extracoes']} extrações em {sonda['segundos']:.1f} s "
                        f"(origem {sonda['origem']})")
        elif cfg["situacao"] == "limite":
            situacao = f"medido; parou no limite de {cfg['limite']:.0f} s"
        else:
            situacao = "medido"
        if cfg["tempos_c"]:
            interno = sum(cfg["tempos_c"]) / len(cfg["tempos_c"])
            situacao += f"; {interno:.4g} s dentro do C"
        linhas.append(f"| {cfg['motor']} | {cfg['fila']} | {len(cfg['tempos'])} | {total} | "
                      f"{formatar_segundos(valor, estimado)} | {situacao} |")
    linhas += ["", "Origens: " + ", ".join(map(str, resultado["origens"]))]
    return "\n".join(linhas)


def tabela_comparativa(resultados):
    nomes = [nome_configuracao(m, f) for m, f in CONFIGURACOES]
    linhas = ["| grafo | vértices | " + " | ".join(f"{nome} (s)" for nome in nomes)
              + " | vetor ÷ heap (C) | vetor ÷ heap (Python) | Python ÷ C (heap) | Python ÷ C (vetor) |",
              "|---|---|" + "---|" * (len(nomes) + 4)]
    for resultado in resultados:
        medias = {nome_configuracao(c["motor"], c["fila"]): media(c) for c in resultado["configuracoes"]}

        def razao(a, b):
            if a not in medias or b not in medias or None in (medias[a][0], medias[b][0]):
                return "-"
            estimado = medias[a][1] or medias[b][1]
            return f"{'≈ ' if estimado else ''}{medias[a][0] / medias[b][0]:.3g}×"

        celulas = [formatar_segundos(*medias[nome]) if nome in medias else "-" for nome in nomes]
        celulas += [razao("c-vetor", "c-heap"), razao("python-vetor", "python-heap"),
                    razao("python-heap", "c-heap"), razao("python-vetor", "c-vetor")]
        linhas.append(f"| {resultado['grafo']} | {resultado['vertices']} | " + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def escrever_tabelas(pasta, saida):
    resultados = [json.loads(arquivo.read_text(encoding="utf-8"))
                  for arquivo in sorted(Path(pasta).glob("*.json"))]
    partes = ["# Estudos de caso — Parte 2", "",
              "Tempo médio de Dijkstra por origem. ≈ marca estimativas (ver a situação de cada "
              "grafo); as razões dizem quantas vezes a segunda configuração é mais rápida.", "",
              tabela_comparativa(resultados), ""]
    for resultado in resultados:
        partes += [markdown_grafo(resultado), ""]
    if resultados:
        info = resultados[-1]["ambiente"]
        partes.append("Ambiente: " + "; ".join(f"{chave}: {valor}" for chave, valor in info.items()))
    Path(saida).write_text("\n".join(partes) + "\n", encoding="utf-8")


def estudo_grafo(nome, k=100, semente=242, representacao="lista", **opcoes):
    """Compatível com a versão anterior: devolve a seção Markdown do grafo."""
    return markdown_grafo(executar_estudo(nome, k, semente, representacao, **opcoes))


def ler_pares(pares, conversao):
    valores = {}
    for par in pares:
        nome, _, valor = par.partition("=")
        if nome not in {nome_configuracao(m, f) for m, f in CONFIGURACOES} or not valor:
            raise SystemExit(f"Use configuração=valor, por exemplo python-vetor=3 (recebido: {par}).")
        valores[nome] = conversao(valor)
    return valores


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("grafos", nargs="+")
    parser.add_argument("--k", type=int, default=100, help="origens sorteadas (padrão 100)")
    parser.add_argument("--semente", type=int, default=242)
    parser.add_argument("--representacao", choices=("csr", "lista", "matriz"), default="csr")
    parser.add_argument("--motores", default=None, help="python,c (padrão: os dois com csr)")
    parser.add_argument("--filas", default="vetor,heap")
    parser.add_argument("--leitor", choices=("c", "numpy"), default=None,
                        help="leitor do CSR (padrão: c, se compilado)")
    parser.add_argument("--limite", type=float, default=900,
                        help="segundos por configuração e grafo; 0 = sem limite (padrão 900)")
    parser.add_argument("--sonda", type=float, default=60,
                        help="segundos da execução parcial que decide entre medir e estimar")
    parser.add_argument("--k-config", nargs="*", default=[], metavar="CONFIG=K",
                        help="k específico, por exemplo python-vetor=3")
    parser.add_argument("--limite-config", nargs="*", default=[], metavar="CONFIG=SEGUNDOS")
    parser.add_argument("--cpu", type=int, default=None,
                        help="fixa o processo neste núcleo (use um núcleo de desempenho)")
    parser.add_argument("--resultados", default="resultados_p2")
    parser.add_argument("--saida", default="tabelas_p2.md")
    args = parser.parse_args()

    disponivel_c = False
    if args.representacao == "csr":
        from motor_c import disponivel
        disponivel_c = disponivel()
    motores = tuple(args.motores.split(",")) if args.motores else (
        ("c", "python") if disponivel_c else ("python",))
    leitor = args.leitor or ("c" if disponivel_c else "numpy")
    if args.cpu is not None:
        os.sched_setaffinity(0, {args.cpu})
    pasta = Path(args.resultados)
    pasta.mkdir(exist_ok=True)
    for nome in args.grafos:
        resultado = executar_estudo(
            nome, args.k, args.semente, args.representacao, motores=motores,
            filas=tuple(args.filas.split(",")), limite=args.limite or None, sonda=args.sonda,
            leitor=leitor, k_config=ler_pares(args.k_config, int),
            limite_config=ler_pares(args.limite_config, float))
        # Grava cada grafo concluído, preservando resultados de execuções longas.
        destino = pasta / f"{Path(nome).name}.json"
        destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
        escrever_tabelas(pasta, args.saida)
        print(f"Resultados em {destino} e {args.saida}", flush=True)


if __name__ == "__main__":
    main()
