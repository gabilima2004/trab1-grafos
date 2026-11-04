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
import statistics
import threading
from array import array
from contextlib import contextmanager
from datetime import datetime
from math import inf, isinf, sqrt
from pathlib import Path
from time import perf_counter, sleep

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


class GuardaDeTomada:
    """Faz as medições acontecerem só com o computador na tomada.

    Na bateria, o processador reduz a frequência: o mesmo Dijkstra ficou de
    11% (C com heap) a 56% (Python com heap) mais lento. Antes de cada medição, a guarda espera a
    tomada; durante a medição, uma thread confere a tomada a cada segundo, e
    a medição que pegar algum momento na bateria é descartada e repetida.
    """

    def __init__(self, arquivo_online, avisar=print, intervalo=15.0):
        self.arquivo_online = Path(arquivo_online)
        self.avisar = avisar
        self.intervalo = intervalo
        self.repeticoes = 0

    @classmethod
    def do_sistema(cls, avisar=print):
        """Guarda da fonte externa (tipo Mains) do Linux, ou None se não houver."""
        for fonte in sorted(Path("/sys/class/power_supply").glob("*")):
            try:
                if (fonte / "type").read_text().strip() == "Mains":
                    return cls(fonte / "online", avisar)
            except OSError:
                continue
        return None

    def na_tomada(self):
        return self.arquivo_online.read_text().strip() == "1"

    def aguardar(self):
        if self.na_tomada():
            return
        self.avisar("Na bateria: medições pausadas até o computador voltar à tomada.", flush=True)
        while not self.na_tomada():
            sleep(self.intervalo)
        self.avisar("Na tomada de novo: medições retomadas.", flush=True)

    def medir(self, funcao, descricao):
        """Executa funcao() na tomada e a repete se a bateria entrar no meio."""
        while True:
            self.aguardar()
            sempre_na_tomada = [True]
            parar = threading.Event()

            def vigiar():
                while not parar.wait(1.0):
                    if not self.na_tomada():
                        sempre_na_tomada[0] = False

            vigia = threading.Thread(target=vigiar, daemon=True)
            vigia.start()
            try:
                resultado = funcao()
            finally:
                parar.set()
                vigia.join()
            if sempre_na_tomada[0] and self.na_tomada():
                return resultado
            self.repeticoes += 1
            self.avisar(f"{descricao}: a bateria entrou durante a medição; repetindo.", flush=True)


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


def decidir_por_sonda(grafo, estado, origem, sonda, alcance, numero_vertices, medir):
    """Executa uma sonda e decide entre medir ou estimar a configuração."""
    orcamento = min(sonda, estado["limite"])
    segundos, extracoes, completa = medir(
        lambda: sondar(grafo, estado["motor"], estado["fila"], origem, orcamento),
        f"sonda {nome_configuracao(estado['motor'], estado['fila'])}")
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
                    k_config=None, limite_config=None, avisar=print, guarda=None):
    """Roda os dois estudos de caso em um grafo e devolve um dicionário.

    guarda (GuardaDeTomada), se informada, só deixa medir na tomada.
    """

    def medir(funcao, descricao):
        return guarda.medir(funcao, f"{titulo} {descricao}") if guarda else funcao()

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
                decidir_por_sonda(grafo, estado, origem, sonda, alcance, n, medir)
            if not estado["_ativa"]:
                continue
            segundos, segundos_c, resultado = medir(
                lambda: executar(grafo, estado["motor"], estado["fila"], origem),
                f"[{nome_configuracao(estado['motor'], estado['fila'])}] origem {origem}")
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
            "caminhos": caminhos, "configuracoes": estados, "so_na_tomada": guarda is not None,
            "medicoes_repetidas": guarda.repeticoes if guarda else 0, "ambiente": ambiente()}


def formatar_segundos(valor, estimado=False):
    if valor is None:
        return "-"
    return f"{'≈ ' if estimado else ''}{valor:.4g}"


def media(configuracao):
    if configuracao["tempos"]:
        return sum(configuracao["tempos"]) / len(configuracao["tempos"]), False
    return configuracao["estimativa_media"], True


# Quantis da t de Student (bilateral, 95%) por graus de liberdade. Entre duas
# entradas vale a de menos graus (intervalo um pouco mais largo); acima de
# 120, o da normal.
QUANTIS_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
               9: 2.262, 10: 2.228, 15: 2.131, 20: 2.086, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}


def dispersao(tempos):
    """Desvio padrão amostral e meia-largura do intervalo de 95% da média."""
    if len(tempos) < 2:
        return None, None
    desvio = statistics.stdev(tempos)
    graus = len(tempos) - 1
    quantil = 1.960 if graus > 120 else QUANTIS_T95[max(g for g in QUANTIS_T95 if g <= graus)]
    return desvio, quantil * desvio / sqrt(len(tempos))


def energia(resultado):
    """Como a energia ficou durante a medição (ver GuardaDeTomada).

    Resultados medidos antes da guarda trazem uma observação escrita à parte.
    """
    if resultado.get("so_na_tomada"):
        return (f"Medido só na tomada; {resultado['medicoes_repetidas']} execuções repetidas "
                "por pegarem bateria.")
    return resultado.get("observacao", "Medido sem a guarda de tomada.")


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
               f"alcançados por origem. {energia(resultado)}", "",
               "| motor | fila | origens medidas | tempo total (s) | tempo médio (s) | desvio padrão (s) "
               "| IC 95% (s) | situação |",
               "|---|---|---|---|---|---|---|---|"]
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
        desvio, intervalo = dispersao(cfg["tempos"])
        intervalo = f"± {intervalo:.2g}" if intervalo is not None else "-"
        linhas.append(f"| {cfg['motor']} | {cfg['fila']} | {len(cfg['tempos'])} | {total} | "
                      f"{formatar_segundos(valor, estimado)} | {formatar_segundos(desvio)} | {intervalo} | "
                      f"{situacao} |")
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


def carregar_perfis(pasta):
    """Perfis de recursos gravados por perfil_p2.py, por nome do grafo."""
    perfis = (json.loads(arquivo.read_text(encoding="utf-8"))
              for arquivo in sorted((Path(pasta) / "perfil").glob("*.json")))
    return {perfil["grafo"]: perfil for perfil in perfis}


def operacoes_medias(perfil):
    contagens = perfil["contagens"]
    return {chave: sum(c[chave] for c in contagens) / len(contagens)
            for chave in ("extracoes", "atualizacoes", "arcos_examinados")}


def custos_por_operacao(resultado, perfil):
    """Vetor: ns por vértice percorrido (cada extração percorre os n vértices).
    Heap: milhões de arcos examinados por segundo. Devolve {config: (valor, estimado)}."""
    operacoes = operacoes_medias(perfil)
    custos = {}
    for cfg in resultado["configuracoes"]:
        valor, estimado = media(cfg)
        if valor is None:
            continue
        nome = nome_configuracao(cfg["motor"], cfg["fila"])
        if cfg["fila"] == "vetor":
            custos[nome] = (valor / (operacoes["extracoes"] * resultado["vertices"]) * 1e9, estimado)
        else:
            custos[nome] = (operacoes["arcos_examinados"] / valor / 1e6, estimado)
    return custos


def markdown_recursos(resultados, perfis):
    linhas = ["## Memória, CPU e operações", "",
              "Uma execução por configuração, a partir da primeira origem do estudo, num processo "
              "novo (perfil_p2.py). O pico de memória inclui os vetores de saída e as estruturas da "
              "fila, mas não o grafo. As configurações estimadas no estudo de tempos rodam por um "
              "prazo curto (execução parcial). CPU, trocas de contexto e faltas de página são da "
              "thread que executa Dijkstra.", "",
              "| grafo | motor | fila | pico de memória (MB) | bytes por vértice | CPU usuário (s) | "
              "CPU sistema (s) | parede (s) | trocas involuntárias | faltas de página (menores/maiores) "
              "| execução |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for resultado in resultados:
        perfil = perfis.get(resultado["grafo"])
        for medida in perfil["medidas"] if perfil else ():
            por_vertice = medida["pico_mb"] * 2 ** 20 / perfil["vertices"]
            execucao = "completa" if medida["completa"] else f"parcial ({medida['extracoes']} extrações)"
            linhas.append(f"| {resultado['grafo']} | {medida['motor']} | {medida['fila']} | "
                          f"{medida['pico_mb']:.1f} | {por_vertice:.1f} | {medida['cpu_usuario']:.3f} | "
                          f"{medida['cpu_sistema']:.3f} | {medida['parede']:.3f} | "
                          f"{medida['trocas_involuntarias']} | {medida['faltas_menores']}/"
                          f"{medida['faltas_maiores']} | {execucao} |")
    linhas += ["", "Operações por origem (média das origens contadas, motor C) e custo por operação: no "
               "vetor, nanossegundos por vértice percorrido; no heap, milhões de arcos examinados por "
               "segundo.", "",
               "| grafo | extrações | atualizações | arcos examinados | atualizações por arco | "
               "C heap (Marcos/s) | Python heap (Marcos/s) | C vetor (ns/vértice) | "
               "Python vetor (ns/vértice) |",
               "|---|---|---|---|---|---|---|---|---|"]
    for resultado in resultados:
        perfil = perfis.get(resultado["grafo"])
        if not perfil:
            continue
        operacoes = operacoes_medias(perfil)
        custos = custos_por_operacao(resultado, perfil)
        celulas = [formatar_segundos(*custos[nome]) if nome in custos else "-"
                   for nome in ("c-heap", "python-heap", "c-vetor", "python-vetor")]
        linhas.append(f"| {resultado['grafo']} | {operacoes['extracoes']:.0f} | "
                      f"{operacoes['atualizacoes']:.0f} | {operacoes['arcos_examinados']:.0f} | "
                      f"{operacoes['atualizacoes'] / operacoes['arcos_examinados']:.3f} | "
                      + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def escrever_tabelas(pasta, saida):
    resultados = [json.loads(arquivo.read_text(encoding="utf-8"))
                  for arquivo in sorted(Path(pasta).glob("*.json"))]
    partes = ["# Estudos de caso — Parte 2", "",
              "Tempo médio de Dijkstra por origem. ≈ marca estimativas (ver a situação de cada "
              "grafo); as razões dizem quantas vezes a segunda configuração é mais rápida.", "",
              tabela_comparativa(resultados), ""]
    perfis = carregar_perfis(pasta)
    if perfis:
        partes += [markdown_recursos(resultados, perfis), ""]
    partes += ["## Grafos", ""]
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
    parser.add_argument("grafos", nargs="*")
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
    parser.add_argument("--permitir-bateria", action="store_true",
                        help="mede mesmo na bateria (por padrão, espera a tomada)")
    parser.add_argument("--apenas-tabelas", action="store_true",
                        help="só regenera as tabelas a partir dos resultados gravados")
    args = parser.parse_args()
    if args.apenas_tabelas:
        escrever_tabelas(args.resultados, args.saida)
        return
    if not args.grafos:
        parser.error("informe ao menos um grafo")

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
    guarda = None if args.permitir_bateria else GuardaDeTomada.do_sistema()
    for nome in args.grafos:
        resultado = executar_estudo(
            nome, args.k, args.semente, args.representacao, motores=motores,
            filas=tuple(args.filas.split(",")), limite=args.limite or None, sonda=args.sonda,
            leitor=leitor, k_config=ler_pares(args.k_config, int),
            limite_config=ler_pares(args.limite_config, float), guarda=guarda)
        # Grava cada grafo concluído, preservando resultados de execuções longas.
        destino = pasta / f"{Path(nome).name}.json"
        destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
        escrever_tabelas(pasta, args.saida)
        print(f"Resultados em {destino} e {args.saida}", flush=True)


if __name__ == "__main__":
    main()
