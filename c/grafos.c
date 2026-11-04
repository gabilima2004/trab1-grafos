#define _GNU_SOURCE
#include "grafos.h"

#include <errno.h>
#include <locale.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <zlib.h>

#define TAMANHO_LINHA 4096

struct GrLeitura {
    int32_t n;
    int64_t m;
    int64_t capacidade;
    int32_t *u;
    int32_t *v;
    double *peso;
};

static void mensagem(char *erro, size_t tamanho, const char *formato, ...)
{
    if (erro == NULL || tamanho == 0)
        return;
    va_list argumentos;
    va_start(argumentos, formato);
    vsnprintf(erro, tamanho, formato, argumentos);
    va_end(argumentos);
}

static int eh_espaco(char c)
{
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f';
}

static int separar_campos(char *linha, char **campos, int maximo)
{
    int total = 0;
    char *p = linha;
    for (;;) {
        while (eh_espaco(*p))
            p++;
        if (*p == '\0')
            return total;
        if (total < maximo)
            campos[total] = p;
        total++;
        while (*p != '\0' && !eh_espaco(*p))
            p++;
        if (*p == '\0')
            return total;
        *p++ = '\0';
    }
}

static int ler_inteiro(const char *s, int64_t *valor)
{
    int negativo = (*s == '-');
    if (*s == '-' || *s == '+')
        s++;
    if (*s == '\0')
        return 0;
    int64_t x = 0;
    for (; *s != '\0'; s++) {
        if (*s < '0' || *s > '9')
            return 0;
        if (x < INT64_C(1000000000000))
            x = 10 * x + (*s - '0');
    }
    *valor = negativo ? -x : x;
    return 1;
}

static locale_t locale_c(void)
{
    static locale_t c = (locale_t) 0;
    if (c == (locale_t) 0)
        c = newlocale(LC_NUMERIC_MASK, "C", (locale_t) 0);
    return c;
}

static int crescer(GrLeitura *leitura)
{
    int64_t nova = leitura->capacidade ? 2 * leitura->capacidade : (INT64_C(1) << 16);
    int32_t *u = realloc(leitura->u, (size_t) nova * sizeof *u);
    if (u == NULL)
        return 0;
    leitura->u = u;
    int32_t *v = realloc(leitura->v, (size_t) nova * sizeof *v);
    if (v == NULL)
        return 0;
    leitura->v = v;
    double *peso = realloc(leitura->peso, (size_t) nova * sizeof *peso);
    if (peso == NULL)
        return 0;
    leitura->peso = peso;
    leitura->capacidade = nova;
    return 1;
}

void gr_liberar_leitura(GrLeitura *leitura)
{
    if (leitura == NULL)
        return;
    free(leitura->u);
    free(leitura->v);
    free(leitura->peso);
    free(leitura);
}

int32_t gr_leitura_vertices(const GrLeitura *leitura) { return leitura->n; }
int64_t gr_leitura_arestas(const GrLeitura *leitura) { return leitura->m; }

static int proxima_linha(gzFile arquivo, char *linha)
{
    if (gzgets(arquivo, linha, TAMANHO_LINHA) == NULL)
        return 0;
    size_t tamanho = strlen(linha);
    if (tamanho == TAMANHO_LINHA - 1 && linha[tamanho - 1] != '\n' && !gzeof(arquivo))
        return -1;
    return 1;
}

#define FALHAR(codigo_erro, ...)                              \
    do {                                                      \
        *codigo = (codigo_erro);                              \
        mensagem(erro, tamanho_erro, __VA_ARGS__);            \
        goto falha;                                           \
    } while (0)

static int erro_de_leitura(gzFile arquivo, const char *caminho, char *erro, size_t tamanho_erro)
{
    int codigo_zlib;
    const char *texto = gzerror(arquivo, &codigo_zlib);
    if (codigo_zlib == Z_OK)
        return 0;
    mensagem(erro, tamanho_erro, "Erro ao ler %s: %s.", caminho,
             codigo_zlib == Z_ERRNO ? strerror(errno) : texto);
    return 1;
}

GrLeitura *gr_ler_arestas(const char *caminho, int *codigo, char *erro, size_t tamanho_erro)
{
    char linha[TAMANHO_LINHA];
    char *campos[3];
    int64_t numero_linha = 1;
    int64_t n = 0;
    int situacao;
    GrLeitura *leitura = NULL;
    locale_t c = locale_c();

    *codigo = GR_OK;
    if (c == (locale_t) 0) {
        *codigo = GR_ERRO_MEMORIA;
        mensagem(erro, tamanho_erro, "Memória insuficiente.");
        return NULL;
    }
    gzFile arquivo = gzopen(caminho, "rb");
    if (arquivo == NULL) {
        *codigo = GR_ERRO_ARQUIVO;
        mensagem(erro, tamanho_erro, "Não foi possível abrir %s: %s.", caminho, strerror(errno));
        return NULL;
    }
    gzbuffer(arquivo, 1 << 20);

    leitura = calloc(1, sizeof *leitura);
    if (leitura == NULL)
        FALHAR(GR_ERRO_MEMORIA, "Memória insuficiente.");
    situacao = proxima_linha(arquivo, linha);
    if (situacao == 0 && erro_de_leitura(arquivo, caminho, erro, tamanho_erro)) {
        *codigo = GR_ERRO_ARQUIVO;
        goto falha;
    }
    if (situacao <= 0 || separar_campos(linha, campos, 1) != 1 || !ler_inteiro(campos[0], &n)
            || n < 0 || n > INT32_MAX - 2)
        FALHAR(GR_ERRO_FORMATO, "Linha 1: número de vértices inválido.");
    leitura->n = (int32_t) n;

    while ((situacao = proxima_linha(arquivo, linha)) != 0) {
        numero_linha++;
        if (situacao < 0)
            FALHAR(GR_ERRO_FORMATO, "Linha %lld: linha longa demais.", (long long) numero_linha);
        int total = separar_campos(linha, campos, 3);
        if (total == 0)
            continue;
        if (total != 3)
            FALHAR(GR_ERRO_FORMATO, "Linha %lld: número de colunas inválido.", (long long) numero_linha);
        int64_t extremos[2];
        for (int i = 0; i < 2; i++) {
            if (!ler_inteiro(campos[i], &extremos[i]))
                FALHAR(GR_ERRO_FORMATO, "Linha %lld: vértice inválido '%s'.",
                       (long long) numero_linha, campos[i]);
            if (extremos[i] < 1 || extremos[i] > n)
                FALHAR(GR_ERRO_FORMATO, "Linha %lld: Vértice %lld fora do intervalo 1..%lld.",
                       (long long) numero_linha, (long long) extremos[i], (long long) n);
        }
        char *fim;
        double peso = strtod_l(campos[2], &fim, c);
        if (fim == campos[2] || *fim != '\0')
            FALHAR(GR_ERRO_FORMATO, "Linha %lld: peso inválido '%s'.", (long long) numero_linha, campos[2]);
        if (!isfinite(peso))
            FALHAR(GR_ERRO_FORMATO, "Linha %lld: O peso deve ser um número real finito.",
                   (long long) numero_linha);
        if (leitura->m == leitura->capacidade && !crescer(leitura))
            FALHAR(GR_ERRO_MEMORIA, "Memória insuficiente.");
        leitura->u[leitura->m] = (int32_t) extremos[0];
        leitura->v[leitura->m] = (int32_t) extremos[1];
        leitura->peso[leitura->m] = peso;
        leitura->m++;
    }
    if (erro_de_leitura(arquivo, caminho, erro, tamanho_erro)) {
        *codigo = GR_ERRO_ARQUIVO;
        goto falha;
    }
    gzclose(arquivo);
    return leitura;

falha:
    gzclose(arquivo);
    gr_liberar_leitura(leitura);
    return NULL;
}

int gr_montar_csr(const GrLeitura *leitura, int64_t *inicio, int32_t *adjacentes, double *pesos)
{
    int32_t n = leitura->n;
    int64_t m = leitura->m;
    memset(inicio, 0, ((size_t) n + 2) * sizeof *inicio);
    for (int64_t e = 0; e < m; e++) {
        inicio[leitura->u[e] + 1]++;
        inicio[leitura->v[e] + 1]++;
    }
    for (int64_t x = 1; x <= (int64_t) n + 1; x++)
        inicio[x] += inicio[x - 1];
    int64_t *proximo = malloc(((size_t) n + 1) * sizeof *proximo);
    if (proximo == NULL)
        return GR_ERRO_MEMORIA;
    memcpy(proximo, inicio, ((size_t) n + 1) * sizeof *proximo);
    for (int64_t e = 0; e < m; e++) {
        int32_t u = leitura->u[e], v = leitura->v[e];
        double peso = leitura->peso[e];
        int64_t p = proximo[u]++;
        adjacentes[p] = v;
        pesos[p] = peso;
        p = proximo[v]++;
        adjacentes[p] = u;
        pesos[p] = peso;
    }
    free(proximo);
    return GR_OK;
}

typedef struct Fila Fila;
struct Fila {
    void (*atualizar)(Fila *fila, int32_t v);
    int32_t (*extrair_minimo)(Fila *fila);
    const double *dist;
    int32_t n;
    double *chave;
    int64_t ativos;
    int32_t *heap;
    int32_t *posicao;
    int32_t tamanho;
    int32_t (*extrair_sem_prazo)(Fila *fila);
    double prazo;
    void (*atualizar_sem_contagem)(Fila *fila, int32_t v);
    int64_t atualizacoes;
};

static void vetor_atualizar(Fila *fila, int32_t v)
{
    if (fila->chave[v] == INFINITY)
        fila->ativos++;
    fila->chave[v] = fila->dist[v];
}

enum { BLOCO = 64 };

static int32_t vetor_extrair_minimo(Fila *fila)
{
    if (fila->ativos == 0)
        return 0;
    const double *chave = fila->chave;
    const int64_t n = fila->n;
    double melhor = INFINITY;
    int64_t bloco_melhor = 1;
    for (int64_t bloco = 1; bloco <= n; bloco += BLOCO) {
        int64_t fim = n - bloco >= BLOCO ? bloco + BLOCO : n + 1;
        double minimo = INFINITY;
#pragma omp simd reduction(min : minimo)
        for (int64_t v = bloco; v < fim; v++)
            minimo = chave[v] < minimo ? chave[v] : minimo;
        if (minimo < melhor) {
            melhor = minimo;
            bloco_melhor = bloco;
        }
    }
    int32_t menor = (int32_t) bloco_melhor;
    while (chave[menor] != melhor)
        menor++;
    fila->chave[menor] = INFINITY;
    fila->ativos--;
    return menor;
}

static int precede(const double *dist, int32_t a, int32_t b)
{
    return dist[a] < dist[b] || (dist[a] == dist[b] && a < b);
}

static void heap_atualizar(Fila *fila, int32_t v)
{
    int32_t *heap = fila->heap;
    int32_t i = fila->posicao[v];
    if (i < 0)
        i = fila->tamanho++;
    while (i > 0) {
        int32_t p = (i - 1) / 2;
        if (!precede(fila->dist, v, heap[p]))
            break;
        heap[i] = heap[p];
        fila->posicao[heap[i]] = i;
        i = p;
    }
    heap[i] = v;
    fila->posicao[v] = i;
}

static int32_t heap_extrair_minimo(Fila *fila)
{
    if (fila->tamanho == 0)
        return 0;
    int32_t *heap = fila->heap;
    int32_t minimo = heap[0];
    fila->posicao[minimo] = -1;
    int32_t ultimo = heap[--fila->tamanho];
    if (fila->tamanho > 0) {
        int32_t i = 0;
        for (;;) {
            int32_t filho = 2 * i + 1;
            if (filho >= fila->tamanho)
                break;
            if (filho + 1 < fila->tamanho && precede(fila->dist, heap[filho + 1], heap[filho]))
                filho++;
            if (!precede(fila->dist, heap[filho], ultimo))
                break;
            heap[i] = heap[filho];
            fila->posicao[heap[i]] = i;
            i = filho;
        }
        heap[i] = ultimo;
        fila->posicao[ultimo] = i;
    }
    return minimo;
}

static double agora(void);

static int32_t extrair_com_prazo(Fila *fila)
{
    if (agora() >= fila->prazo)
        return 0;
    return fila->extrair_sem_prazo(fila);
}

static void atualizar_contando(Fila *fila, int32_t v)
{
    fila->atualizacoes++;
    fila->atualizar_sem_contagem(fila, v);
}

static void liberar_fila(Fila *fila)
{
    free(fila->chave);
    free(fila->heap);
    free(fila->posicao);
}

static int criar_fila(Fila *fila, int tipo, const double *dist, int32_t n)
{
    memset(fila, 0, sizeof *fila);
    fila->dist = dist;
    fila->n = n;
    if (tipo == GR_FILA_VETOR) {
        fila->atualizar = vetor_atualizar;
        fila->extrair_minimo = vetor_extrair_minimo;
        fila->chave = malloc(((size_t) n + 1) * sizeof *fila->chave);
        if (fila->chave == NULL)
            return GR_ERRO_MEMORIA;
        for (int32_t v = 0; v <= n; v++)
            fila->chave[v] = INFINITY;
    } else {
        fila->atualizar = heap_atualizar;
        fila->extrair_minimo = heap_extrair_minimo;
        fila->heap = malloc(((size_t) n + 1) * sizeof *fila->heap);
        fila->posicao = malloc(((size_t) n + 1) * sizeof *fila->posicao);
        if (fila->heap == NULL || fila->posicao == NULL) {
            liberar_fila(fila);
            return GR_ERRO_MEMORIA;
        }
        memset(fila->posicao, 0xff, ((size_t) n + 1) * sizeof *fila->posicao);
    }
    return GR_OK;
}

static double agora(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double) t.tv_sec + 1e-9 * (double) t.tv_nsec;
}

int gr_dijkstra(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                const double *pesos, int32_t origem, int tipo_fila,
                double *dist, int32_t *pai, double limite_segundos,
                int64_t *extracoes, int64_t *atualizacoes, double *segundos)
{
    double comeco = agora();
    if (origem < 1 || origem > n)
        return GR_ERRO_ORIGEM;
    if (tipo_fila != GR_FILA_VETOR && tipo_fila != GR_FILA_HEAP)
        return GR_ERRO_FILA;

    Fila fila;
    unsigned char *finalizado = calloc((size_t) n + 1, 1);
    if (finalizado == NULL)
        return GR_ERRO_MEMORIA;
    if (criar_fila(&fila, tipo_fila, dist, n) != GR_OK) {
        free(finalizado);
        return GR_ERRO_MEMORIA;
    }
    for (int32_t v = 0; v <= n; v++) {
        dist[v] = INFINITY;
        pai[v] = 0;
    }

    if (limite_segundos > 0) {
        fila.extrair_sem_prazo = fila.extrair_minimo;
        fila.extrair_minimo = extrair_com_prazo;
        fila.prazo = comeco + limite_segundos;
    }
    if (atualizacoes != NULL) {
        fila.atualizar_sem_contagem = fila.atualizar;
        fila.atualizar = atualizar_contando;
    }

    dist[origem] = 0.0;
    fila.atualizar(&fila, origem);
    int64_t extraidos = 0;
    int32_t u;
    while ((u = fila.extrair_minimo(&fila)) != 0) {
        extraidos++;
        finalizado[u] = 1;
        double du = dist[u];
        for (int64_t e = inicio[u]; e < inicio[u + 1]; e++) {
            int32_t v = adjacentes[e];
            double candidata = du + pesos[e];
            if (!finalizado[v] && candidata < dist[v]) {
                dist[v] = candidata;
                pai[v] = u;
                fila.atualizar(&fila, v);
            }
        }
    }

    liberar_fila(&fila);
    free(finalizado);
    if (extracoes != NULL)
        *extracoes = extraidos;
    if (atualizacoes != NULL)
        *atualizacoes = fila.atualizacoes;
    if (segundos != NULL)
        *segundos = agora() - comeco;
    return GR_OK;
}

#ifndef GR_OPCOES
#define GR_OPCOES "?"
#endif

const char *gr_compilacao(void)
{
#ifdef __VERSION__
    return "cc " __VERSION__ "; " GR_OPCOES;
#else
    return GR_OPCOES;
#endif
}
