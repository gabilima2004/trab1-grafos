"""Cronometra um grafo e um algoritmo, com checkpoint por rodada."""
import argparse
import ctypes
from contextlib import contextmanager
import gzip
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
from statistics import mean
from time import perf_counter

import numpy as np

from caminhos_p3 import bellman_ford, floyd_warshall
from experimentos_p3 import NOMES, VERTICES, todos_pares_bellman_ford
from grafo_csr import ler_grafo_csr

RODADAS = 10
MIB = 2**20
GIB = 2**30


def memoria_disponivel():
    if os.name == "nt":
        class Estado(ctypes.Structure):
            _fields_ = [("tamanho", ctypes.c_ulong), ("carga", ctypes.c_ulong)] + [
                (nome, ctypes.c_uint64) for nome in (
                    "total", "disponivel", "pagina_total", "pagina_livre",
                    "virtual_total", "virtual_livre", "virtual_extra")]
        estado = Estado()
        estado.tamanho = ctypes.sizeof(estado)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
            return estado.disponivel
    elif platform.system() == "Linux":
        meminfo = Path("/proc/meminfo").read_text(encoding="ascii").splitlines()
        disponivel = next(int(linha.split()[1]) * 1024 for linha in meminfo
                          if linha.startswith("MemAvailable:"))
        # Cgroups v2 no Linux, inclusive em contêineres com namespace próprio.
        raiz = Path("/sys/fs/cgroup")
        grupos = [raiz]
        for linha in Path("/proc/self/cgroup").read_text().splitlines():
            if linha.startswith("0::"):
                atual = raiz / linha[3:].lstrip("/")
                grupos.extend([atual, *(p for p in atual.parents if raiz in p.parents)])
        for grupo in grupos:
            limite, uso = grupo / "memory.max", grupo / "memory.current"
            if limite.is_file() and uso.is_file():
                valor = limite.read_text().strip()
                if valor != "max":
                    disponivel = min(disponivel, max(0, int(valor) - int(uso.read_text())))
        return disponivel
    return None


def exigir_memoria(estimado, teto, etapa):
    automatico = memoria_disponivel()
    limites = [valor for valor in (teto, None if automatico is None else automatico * 8 // 10)
               if valor is not None]
    if not limites:
        raise MemoryError("Memoria disponivel desconhecida. Informe --memoria-gib.")
    orcamento = min(limites)
    if estimado > orcamento:
        raise MemoryError(f"{etapa}: estimativa {estimado / GIB:.2f} GiB, "
                          f"orcamento {orcamento / GIB:.2f} GiB")


def dimensoes(caminho):
    abrir = gzip.open if caminho.suffix == ".gz" else open
    with abrir(caminho, "rb") as arquivo:
        n = int(arquivo.readline())
        if n < 0:
            raise ValueError("Numero de vertices invalido.")
        # Conta linhas sem manter arestas em memoria. Linhas vazias superestimam.
        m = 0
        ultimo = b""
        while bloco := arquivo.read(4 * MIB):
            m += bloco.count(b"\n")
            ultimo = bloco[-1:]
    return n, m + int(bool(ultimo and ultimo != b"\n"))


def pico_algoritmo(algoritmo, grafo, fluxo):
    n = grafo.numero_vertices
    matriz = (n + 1) ** 2
    if algoritmo == "floyd_warshall":
        return 12 * matriz + 64 * (n + 1)
    graus = np.diff(grafo.inicio)
    lote = min(n, 16384)
    # Particiona sem ordenar todos os graus. A soma limita qualquer lote CSR.
    if lote:
        graus.partition(graus.size - lote)
        arcos_lote = int(graus[-lote:].sum())
    else:
        arcos_lote = 0
    saida = 8 * matriz if algoritmo == "bellman_ford_todos_pares" and not fluxo else 0
    propagacao = 56 * (n + 1) if grafo.tem_peso_negativo else 0
    return saida + 64 * (n + 1) + 120 * arcos_lote + propagacao


def sha256(caminho):
    with caminho.open("rb") as arquivo:
        return hashlib.file_digest(arquivo, "sha256").hexdigest()


def salvar(caminho, estado):
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(estado, arquivo, indent=2, ensure_ascii=True, allow_nan=False)
        arquivo.write("\n")
        arquivo.flush()
        os.fsync(arquivo.fileno())
    temporario.replace(caminho)


@contextmanager
def bloquear_saida(caminho):
    """Um unico processo escreve o checkpoint; o SO libera o bloqueio ao sair."""
    with caminho.with_suffix(caminho.suffix + ".lock").open("a+b") as trava:
        if os.name == "nt":
            import msvcrt

            trava.seek(0)
            try:
                msvcrt.locking(trava.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as erro:
                raise ValueError("Outro processo esta usando esta saida.") from erro
        else:
            import fcntl

            try:
                fcntl.flock(trava.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as erro:
                raise ValueError("Outro processo esta usando esta saida.") from erro
        yield


def descrever_ambiente():
    diretorio = Path(__file__).resolve().parent
    modulos = ("benchmark_p3.py", "caminhos_p3.py", "grafo_csr.py", "experimentos_p3.py", "calibracao_p3.py")
    return dict(sistema=platform.platform(), python=platform.python_version(),
                numpy=np.__version__, computador=platform.node(),
                cpu=platform.processor() or platform.machine(),
                cpus_logicas=os.cpu_count(), codigo={m: sha256(diretorio / m) for m in modulos})


def planejamento(args, n, m, rodadas):
    matriz = (n + 1) ** 2
    if args.algoritmo == "floyd_warshall":
        matriz *= 12
    elif args.algoritmo == "bellman_ford_todos_pares" and not args.fluxo:
        matriz *= 8
    else:
        matriz = 0
    pico = max(48 * m + 40 * (n + 1), matriz + 12 * m + 8 * (n + 2)) + 64 * MIB
    memoria = memoria_disponivel()
    teto = None if args.memoria_gib is None else int(args.memoria_gib * GIB)
    limites = [v for v in (teto, None if memoria is None else memoria * 8 // 10)
               if v is not None]
    orcamento = min(limites) if limites else None
    faixa = None
    if getattr(args, "calibracao", None):
        from calibracao_p3 import estimar, ler
        faixa = estimar(ler(args.calibracao), n, m, args.algoritmo, rodadas)
    return dict(sistema=platform.platform(), vertices=n, linhas_arestas=m,
                algoritmo=args.algoritmo, rodadas=rodadas, matriz_bytes=matriz,
                memoria_disponivel_bytes=memoria, estimativa_preparacao_matriz_bytes=pico,
                orcamento_bytes=orcamento, cabe_no_pre_teste=orcamento is not None and pico <= orcamento,
                estimativa_tempo_s=faixa,
                requer_confirmacao=n > 2000 or (faixa is not None and faixa[1] > 120))


def rodar(args):
    if args.algoritmo != "bellman_ford" and args.destino != 100:
        raise ValueError("--destino se aplica apenas a bellman_ford.")
    if args.fluxo and args.algoritmo != "bellman_ford_todos_pares":
        raise ValueError("--fluxo se aplica apenas a bellman_ford_todos_pares.")
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    config = dict(grafo=args.grafo.name, sha256=sha256(args.grafo), algoritmo=args.algoritmo,
                  destino=args.destino, fluxo=args.fluxo, rodadas=RODADAS,
                  direcionado=True, ambiente=descrever_ambiente())
    if args.saida.exists():
        estado = json.loads(args.saida.read_text(encoding="utf-8"))
        if estado["config"] != config:
            raise ValueError("Checkpoint incompativel. Escolha outro arquivo de saida.")
    else:
        estado = dict(config=config, tempos_s=[], media_s=None, estado="preparando", eventos=[])
        salvar(args.saida, estado)
    tempos = estado["tempos_s"]
    if len(tempos) > RODADAS or any(not np.isfinite(t) or t < 0 for t in tempos):
        raise ValueError("Checkpoint contem tempos invalidos.")
    if len(tempos) == RODADAS:
        if estado["estado"] != "concluido" or estado["media_s"] != mean(tempos):
            raise ValueError("Checkpoint concluido com media inconsistente.")
        print("As dez rodadas ja estao completas.", flush=True)
        return 0
    try:
        n, m = dimensoes(args.grafo)
        plano = planejamento(args, n, m, RODADAS - len(tempos))
        estado["planejamento"] = plano
        salvar(args.saida, estado)
        teto = None if args.memoria_gib is None else int(args.memoria_gib * GIB)
        exigir_memoria(plano["estimativa_preparacao_matriz_bytes"], teto, "preparacao e matrizes")
        if plano["estimativa_tempo_s"] is not None:
            print(f"Estimativa para rodadas restantes (s): {plano['estimativa_tempo_s']}", flush=True)
        if plano["requer_confirmacao"] and not args.confirmar_custo:
            raise ValueError("Execucao potencialmente longa. Use --planejar e --confirmar-custo.")
        if plano["requer_confirmacao"] and plano["estimativa_tempo_s"] is None:
            raise ValueError("Execucao longa exige --calibracao desta maquina.")
        grafo = ler_grafo_csr(args.grafo, direcionado=True,
                              transposto=args.algoritmo != "floyd_warshall")
        # Neste ponto, a memoria livre ja desconta o grafo residente.
        adicional = pico_algoritmo(args.algoritmo, grafo, args.fluxo)
        teto_restante = None if teto is None else max(0, teto - grafo.bytes_ocupados())
        exigir_memoria(adicional + 64 * MIB, teto_restante, "execucao")
        estado.update(vertices=n, arcos=grafo.numero_arestas, estado="executando")
        salvar(args.saida, estado)
        if args.algoritmo == "bellman_ford":
            grafo.validar_vertice(args.destino)
            executar = lambda: bellman_ford(grafo, args.destino, transposto=grafo)
        elif args.algoritmo == "floyd_warshall":
            executar = lambda: floyd_warshall(grafo)
        else:
            executar = lambda: todos_pares_bellman_ford(grafo, grafo, fluxo=args.fluxo)
        amostra = [v for v in VERTICES if v <= n]
        for rodada in range(len(tempos) + 1, RODADAS + 1):
            print(f"{args.grafo.name} {args.algoritmo}: iniciando {rodada}/{RODADAS}", flush=True)
            exigir_memoria(adicional + 64 * MIB, teto_restante, "antes da rodada")
            inicio = perf_counter()
            resultado = executar()
            segundos = perf_counter() - inicio
            if rodada == 1:
                if args.algoritmo == "bellman_ford":
                    dados = {v: numero_json(resultado.distancias[v]) for v in (10, 20, 30) if v <= n}
                else:
                    matriz = resultado.distancias if args.algoritmo == "floyd_warshall" else resultado
                    pequena = matriz if args.fluxo else matriz[np.ix_(amostra, amostra)]
                    dados = dict(vertices=amostra, matriz=[[numero_json(v) for v in linha]
                                                             for linha in pequena])
                estado["amostra"] = dados
            del resultado
            if args.algoritmo != "bellman_ford" and rodada == 1:
                del matriz, pequena
            tempos.append(segundos)
            if rodada == RODADAS:
                estado.update(estado="concluido", media_s=mean(tempos))
            salvar(args.saida, estado)
            print(f"Rodada {rodada} gravada ({segundos:.6f} s)", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        # Rele o checkpoint para publicar somente rodadas gravadas integralmente.
        estado = json.loads(args.saida.read_text(encoding="utf-8"))
        interrompido = isinstance(erro, KeyboardInterrupt)
        estado["eventos"].append(dict(utc=datetime.now(timezone.utc).isoformat(),
                                      tipo=type(erro).__name__, mensagem=str(erro),
                                      rodadas_salvas=len(estado["tempos_s"])))
        if estado["estado"] != "concluido":
            estado["estado"] = "interrompido" if interrompido else "erro"
        salvar(args.saida, estado)
        print(f"{estado['estado']}: {erro}", flush=True)
        return 130 if interrompido else 1


def numero_json(valor):
    valor = float(valor)
    return valor if np.isfinite(valor) else str(valor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grafo", type=Path)
    parser.add_argument("algoritmo", choices=NOMES)
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--planejar", action="store_true", help="Estima custo sem executar.")
    parser.add_argument("--calibracao", type=Path)
    parser.add_argument("--destino", type=int, default=100)
    parser.add_argument("--memoria-gib", type=float)
    parser.add_argument("--confirmar-custo", action="store_true")
    parser.add_argument("--fluxo", action="store_true",
                        help="Calcula todos os pares sem reter a matriz completa.")
    args = parser.parse_args()
    if args.memoria_gib is not None and not (0 < args.memoria_gib < float("inf")):
        parser.error("--memoria-gib deve ser positiva e finita")
    if not args.planejar and args.saida is None:
        parser.error("--saida e obrigatoria para executar.")
    if args.fluxo and args.algoritmo != "bellman_ford_todos_pares":
        parser.error("--fluxo se aplica apenas a bellman_ford_todos_pares.")
    try:
        if args.planejar:
            if args.saida is not None:
                parser.error("--planejar imprime em stdout e nao usa --saida.")
            n, m = dimensoes(args.grafo)
            print(json.dumps(planejamento(args, n, m, RODADAS), indent=2))
            return 0
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        with bloquear_saida(args.saida):
            return rodar(args)
    except (OSError, ValueError, KeyboardInterrupt) as erro:
        print(f"{type(erro).__name__}: {erro}", flush=True)
        return 130 if isinstance(erro, KeyboardInterrupt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
