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

#ifdef _OPENMP
#include <omp.h>
#endif

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

static int numero_threads(int threads)
{
#ifdef _OPENMP
    return threads > 0 ? threads : omp_get_max_threads();
#else
    (void) threads;
    return 1;
#endif
}

int gr_montar_csr_direcionado(const GrLeitura *leitura, int transposto, int64_t *inicio,
                              int32_t *adjacentes, double *pesos)
{
    int32_t n = leitura->n;
    int64_t m = leitura->m;
    const int32_t *origem = transposto ? leitura->v : leitura->u;
    const int32_t *destino = transposto ? leitura->u : leitura->v;
    memset(inicio, 0, ((size_t) n + 2) * sizeof *inicio);
    for (int64_t e = 0; e < m; e++)
        inicio[origem[e] + 1]++;
    for (int64_t x = 1; x <= (int64_t) n + 1; x++)
        inicio[x] += inicio[x - 1];
    int64_t *proximo = malloc(((size_t) n + 1) * sizeof *proximo);
    if (proximo == NULL)
        return GR_ERRO_MEMORIA;
    memcpy(proximo, inicio, ((size_t) n + 1) * sizeof *proximo);
    for (int64_t e = 0; e < m; e++) {
        int64_t p = proximo[origem[e]]++;
        adjacentes[p] = destino[e];
        pesos[p] = leitura->peso[e];
    }
    free(proximo);
    return GR_OK;
}

static void inicializar_float(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                              const double *pesos, double *dist, int32_t *pred, int nt)
{
    size_t t = (size_t) n + 1;
#pragma omp parallel for num_threads(nt) schedule(static)
    for (size_t i = 0; i < t; i++) {
        double *di = dist + i * t;
        int32_t *pi = pred + i * t;
        for (size_t j = 0; j < t; j++) {
            di[j] = INFINITY;
            pi[j] = 0;
        }
        if (i > 0)
            di[i] = 0.0;
    }
    for (int32_t u = 1; u <= n; u++)
        for (int64_t e = inicio[u]; e < inicio[u + 1]; e++) {
            size_t x = (size_t) u * t + (size_t) adjacentes[e];
            if (pesos[e] < dist[x]) {
                dist[x] = pesos[e];
                pred[x] = u;
            }
        }
}

int gr_floyd_warshall_classico(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                               const double *pesos, double *dist, int32_t *pred, int threads)
{
    size_t t = (size_t) n + 1;
    int nt = numero_threads(threads);
    double *linha = malloc(t * sizeof *linha);
    int32_t *pais = malloc(t * sizeof *pais);
    if (linha == NULL || pais == NULL) {
        free(linha);
        free(pais);
        return GR_ERRO_MEMORIA;
    }
    inicializar_float(n, inicio, adjacentes, pesos, dist, pred, nt);
    for (int32_t k = 1; k <= n; k++) {
        memcpy(linha, dist + (size_t) k * t, t * sizeof *linha);
        memcpy(pais, pred + (size_t) k * t, t * sizeof *pais);
#pragma omp parallel for num_threads(nt) schedule(static)
        for (int32_t i = 1; i <= n; i++) {
            double *di = dist + (size_t) i * t;
            int32_t *pi = pred + (size_t) i * t;
            double dik = di[k];
            if (dik == INFINITY)
                continue;
#pragma omp simd
            for (size_t j = 1; j < t; j++) {
                double c = dik + linha[j];
                int melhora = c < di[j];
                di[j] = melhora ? c : di[j];
                pi[j] = melhora ? pais[j] : pi[j];
            }
        }
    }
    free(linha);
    free(pais);
    return GR_OK;
}

static void ladrilho(int32_t *dist, size_t t, int32_t i0, int32_t i1, int32_t j0, int32_t j1,
                     int32_t k0, int32_t k1)
{
    for (int32_t k = k0; k < k1; k++) {
        const int32_t *dk = dist + (size_t) k * t;
        for (int32_t i = i0; i < i1; i++) {
            int32_t *di = dist + (size_t) i * t;
            int32_t dik = di[k];
            if (dik == GR_INF_INTEIRO)
                continue;
#pragma omp simd
            for (int32_t j = j0; j < j1; j++) {
                int32_t dkj = dk[j];
                int32_t c = dik + dkj;
                c = c < GR_NEG_INTEIRO ? GR_NEG_INTEIRO : c;
                c = dkj == GR_INF_INTEIRO ? GR_INF_INTEIRO : c;
                di[j] = c < di[j] ? c : di[j];
            }
        }
    }
}

static void reconstruir_arvores(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                                const int32_t *inteiros, const int32_t *dist, void *pred,
                                int pred16, int nt, int *erro)
{
    size_t t = (size_t) n + 1;
#pragma omp parallel num_threads(nt)
    {
        int32_t *fila = malloc(t * sizeof *fila);
        unsigned char *visto = malloc(t);
        if (fila == NULL || visto == NULL) {
#pragma omp atomic write
            *erro = GR_ERRO_MEMORIA;
        }
#pragma omp for schedule(dynamic, 16)
        for (size_t i = 0; i < t; i++) {
            if (fila == NULL || visto == NULL)
                continue;
            const int32_t *di = dist + i * t;
            int16_t *p16 = (int16_t *) pred + i * t;
            int32_t *p32 = (int32_t *) pred + i * t;
            if (pred16)
                memset(p16, 0, t * sizeof *p16);
            else
                memset(p32, 0, t * sizeof *p32);
            if (i == 0)
                continue;
            memset(visto, 0, t);
            int32_t cabeca = 0, cauda = 0;
            fila[cauda++] = (int32_t) i;
            visto[i] = 1;
            while (cabeca < cauda) {
                int32_t u = fila[cabeca++];
                int32_t du = di[u];
                for (int64_t e = inicio[u]; e < inicio[u + 1]; e++) {
                    int32_t v = adjacentes[e];
                    if (visto[v] || du + inteiros[e] != di[v])
                        continue;
                    visto[v] = 1;
                    fila[cauda++] = v;
                    if (pred16)
                        p16[v] = (int16_t) u;
                    else
                        p32[v] = u;
                }
            }
        }
        free(fila);
        free(visto);
    }
}

int gr_floyd_warshall_blocado(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                              const double *pesos, double escala, int32_t *dist, void *pred,
                              int pred16, int32_t bloco, int threads)
{
    if (bloco < 1 || (pred16 && n > INT16_MAX))
        return GR_ERRO_FORMATO;
    size_t t = (size_t) n + 1;
    int nt = numero_threads(threads);
    int64_t m = inicio[n + 1];
    int32_t *inteiros = malloc((size_t) (m > 0 ? m : 1) * sizeof *inteiros);
    if (inteiros == NULL)
        return GR_ERRO_MEMORIA;
    for (int64_t e = 0; e < m; e++)
        inteiros[e] = (int32_t) llround(pesos[e] * escala);

#pragma omp parallel for num_threads(nt) schedule(static)
    for (size_t i = 0; i < t; i++) {
        int32_t *di = dist + i * t;
        for (size_t j = 0; j < t; j++)
            di[j] = GR_INF_INTEIRO;
        if (i > 0)
            di[i] = 0;
    }
    for (int32_t u = 1; u <= n; u++)
        for (int64_t e = inicio[u]; e < inicio[u + 1]; e++) {
            size_t x = (size_t) u * t + (size_t) adjacentes[e];
            if (inteiros[e] < dist[x])
                dist[x] = inteiros[e];
        }

    int32_t b = bloco;
    int32_t blocos = (n + b - 1) / b;
    for (int32_t r = 0; r < blocos; r++) {
        int32_t k0 = 1 + r * b;
        int32_t k1 = k0 + b < n + 1 ? k0 + b : n + 1;
        ladrilho(dist, t, k0, k1, k0, k1, k0, k1);
#pragma omp parallel for num_threads(nt) schedule(dynamic)
        for (int32_t x = 0; x < 2 * blocos; x++) {
            int32_t outro = x % blocos;
            if (outro == r)
                continue;
            int32_t a0 = 1 + outro * b;
            int32_t a1 = a0 + b < n + 1 ? a0 + b : n + 1;
            if (x < blocos)
                ladrilho(dist, t, k0, k1, a0, a1, k0, k1);
            else
                ladrilho(dist, t, a0, a1, k0, k1, k0, k1);
        }
#pragma omp parallel for num_threads(nt) collapse(2) schedule(static)
        for (int32_t bi = 0; bi < blocos; bi++)
            for (int32_t bj = 0; bj < blocos; bj++) {
                if (bi == r || bj == r)
                    continue;
                int32_t i0 = 1 + bi * b;
                int32_t i1 = i0 + b < n + 1 ? i0 + b : n + 1;
                int32_t j0 = 1 + bj * b;
                int32_t j1 = j0 + b < n + 1 ? j0 + b : n + 1;
                ladrilho(dist, t, i0, i1, j0, j1, k0, k1);
            }
    }

    int erro = GR_OK;
    reconstruir_arvores(n, inicio, adjacentes, inteiros, dist, pred, pred16, nt, &erro);
    free(inteiros);
    return erro;
}

typedef struct {
    double *valores;
    double *peso_sucessor;
    int32_t *fronteira;
    int32_t *proxima;
    int32_t *sementes;
    int32_t *pilha;
    unsigned char *marcado;
    unsigned char *cor;
} AreaBF;

static void liberar_area(AreaBF *a)
{
    free(a->valores);
    free(a->peso_sucessor);
    free(a->fronteira);
    free(a->proxima);
    free(a->sementes);
    free(a->pilha);
    free(a->marcado);
    free(a->cor);
}

static int criar_area(AreaBF *a, int32_t n)
{
    size_t t = (size_t) n + 1;
    a->valores = malloc(t * sizeof *a->valores);
    a->peso_sucessor = malloc(t * sizeof *a->peso_sucessor);
    a->fronteira = malloc(t * sizeof *a->fronteira);
    a->proxima = malloc(t * sizeof *a->proxima);
    a->sementes = malloc(t * sizeof *a->sementes);
    a->pilha = malloc(t * sizeof *a->pilha);
    a->marcado = calloc(t, 1);
    a->cor = malloc(t);
    if (!a->valores || !a->peso_sucessor || !a->fronteira || !a->proxima || !a->sementes
            || !a->pilha || !a->marcado || !a->cor) {
        liberar_area(a);
        return GR_ERRO_MEMORIA;
    }
    return GR_OK;
}

static int32_t ciclos_negativos(int32_t n, const int32_t *sucessor, const double *peso,
                                unsigned char *cor, int32_t *saida)
{
    int32_t total = 0;
    memset(cor, 0, (size_t) n + 1);
    for (int32_t raiz = 1; raiz <= n; raiz++) {
        int32_t u = raiz;
        while (u && !cor[u]) {
            cor[u] = 1;
            u = sucessor[u];
        }
        if (u && cor[u] == 1) {
            long double soma = 0.0L;
            int32_t v = u;
            do {
                soma += peso[v];
                v = sucessor[v];
            } while (v != u);
            if (soma < 0.0L)
                do {
                    saida[total++] = v;
                    v = sucessor[v];
                } while (v != u);
        }
        u = raiz;
        while (u && cor[u] == 1) {
            cor[u] = 2;
            u = sucessor[u];
        }
    }
    return total;
}

static void marcar_afetados(const int64_t *inicio, const int32_t *adjacentes,
                            const int32_t *sementes, int32_t quantidade, double *dist,
                            int32_t *sucessor, int32_t *pilha)
{
    int32_t topo = 0;
    for (int32_t x = 0; x < quantidade; x++) {
        int32_t s = sementes[x];
        if (dist[s] != -INFINITY) {
            dist[s] = -INFINITY;
            sucessor[s] = 0;
            pilha[topo++] = s;
        }
    }
    while (topo > 0) {
        int32_t u = pilha[--topo];
        for (int64_t e = inicio[u]; e < inicio[u + 1]; e++) {
            int32_t v = adjacentes[e];
            if (dist[v] != -INFINITY) {
                dist[v] = -INFINITY;
                sucessor[v] = 0;
                pilha[topo++] = v;
            }
        }
    }
}

static int bf_destino(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                      const double *pesos, int32_t destino, int tem_negativo, double *dist,
                      int32_t *sucessor, AreaBF *a)
{
    int32_t tamanho;
    int ciclo = 0;
    for (int32_t v = 0; v <= n; v++) {
        dist[v] = INFINITY;
        sucessor[v] = 0;
    }
    if (destino == 0) {
        for (int32_t v = 1; v <= n; v++) {
            dist[v] = 0.0;
            a->fronteira[v - 1] = v;
        }
        tamanho = n;
    } else {
        dist[destino] = 0.0;
        a->fronteira[0] = destino;
        tamanho = 1;
    }
    for (int32_t rodada = 1; rodada <= n && tamanho > 0; rodada++) {
        for (int32_t x = 0; x < tamanho; x++)
            a->valores[x] = dist[a->fronteira[x]];
        int32_t novos = 0;
        for (int32_t x = 0; x < tamanho; x++) {
            int32_t u = a->fronteira[x];
            double du = a->valores[x];
            for (int64_t e = inicio[u]; e < inicio[u + 1]; e++) {
                int32_t v = adjacentes[e];
                double c = du + pesos[e];
                if (c < dist[v]) {
                    dist[v] = c;
                    sucessor[v] = u;
                    a->peso_sucessor[v] = pesos[e];
                    if (!a->marcado[v]) {
                        a->marcado[v] = 1;
                        a->proxima[novos++] = v;
                    }
                }
            }
        }
        for (int32_t x = 0; x < novos; x++)
            a->marcado[a->proxima[x]] = 0;
        int32_t *troca = a->fronteira;
        a->fronteira = a->proxima;
        a->proxima = troca;
        tamanho = novos;
        if (tamanho == 0)
            break;
        int32_t quantidade;
        const int32_t *lista;
        if (rodada == n) {
            lista = a->fronteira;
            quantidade = tamanho;
        } else if (tem_negativo && rodada % 16 == 0) {
            quantidade = ciclos_negativos(n, sucessor, a->peso_sucessor, a->cor, a->sementes);
            lista = a->sementes;
        } else {
            continue;
        }
        if (quantidade == 0)
            continue;
        ciclo = 1;
        if (destino == 0)
            return 1;
        marcar_afetados(inicio, adjacentes, lista, quantidade, dist, sucessor, a->pilha);
        int32_t restantes = 0;
        for (int32_t x = 0; x < tamanho; x++)
            if (dist[a->fronteira[x]] != -INFINITY)
                a->fronteira[restantes++] = a->fronteira[x];
        tamanho = restantes;
    }
    return ciclo;
}

static int tem_peso_negativo(int32_t n, const int64_t *inicio, const double *pesos)
{
    for (int64_t e = 0; e < inicio[n + 1]; e++)
        if (pesos[e] < 0)
            return 1;
    return 0;
}

int gr_bellman_ford(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                    const double *pesos, int32_t destino, double *dist, int32_t *sucessor,
                    int32_t *ciclo)
{
    if (destino < 0 || destino > n)
        return GR_ERRO_ORIGEM;
    AreaBF area;
    if (criar_area(&area, n) != GR_OK)
        return GR_ERRO_MEMORIA;
    *ciclo = bf_destino(n, inicio, adjacentes, pesos, destino,
                        tem_peso_negativo(n, inicio, pesos), dist, sucessor, &area);
    liberar_area(&area);
    return GR_OK;
}

int gr_bellman_ford_todos(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                          const double *pesos, double *dist, int32_t *ciclo, int threads)
{
    size_t t = (size_t) n + 1;
    int nt = numero_threads(threads);
    int negativo = tem_peso_negativo(n, inicio, pesos);
    int erro = GR_OK;
    int encontrou = 0;
    for (size_t j = 0; j < t; j++)
        dist[j] = INFINITY;
#pragma omp parallel num_threads(nt) reduction(| : encontrou)
    {
        AreaBF area;
        int32_t *sucessor = malloc(t * sizeof *sucessor);
        int ok = sucessor != NULL && criar_area(&area, n) == GR_OK;
        if (!ok) {
#pragma omp atomic write
            erro = GR_ERRO_MEMORIA;
        }
#pragma omp for schedule(dynamic, 8)
        for (int32_t d = 1; d <= n; d++)
            if (ok)
                encontrou |= bf_destino(n, inicio, adjacentes, pesos, d, negativo,
                                        dist + (size_t) d * t, sucessor, &area);
        if (ok)
            liberar_area(&area);
        free(sucessor);
    }
    *ciclo = encontrou;
    return erro;
}

int gr_johnson(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
               const double *pesos, const double *potencial, double *dist, int32_t *pred,
               int threads)
{
    size_t t = (size_t) n + 1;
    int nt = numero_threads(threads);
    int64_t m = inicio[n + 1];
    double *ajustados = malloc((size_t) (m > 0 ? m : 1) * sizeof *ajustados);
    if (ajustados == NULL)
        return GR_ERRO_MEMORIA;
    for (int32_t u = 1; u <= n; u++)
        for (int64_t e = inicio[u]; e < inicio[u + 1]; e++) {
            double c = pesos[e] + potencial[u] - potencial[adjacentes[e]];
            ajustados[e] = c < 0 ? 0.0 : c;
        }
    for (size_t j = 0; j < t; j++) {
        dist[j] = INFINITY;
        pred[j] = 0;
    }
    int erro = GR_OK;
#pragma omp parallel for num_threads(nt) schedule(dynamic, 8)
    for (int32_t s = 1; s <= n; s++) {
        double *ds = dist + (size_t) s * t;
        int32_t *ps = pred + (size_t) s * t;
        int r = gr_dijkstra(n, inicio, adjacentes, ajustados, s, GR_FILA_HEAP, ds, ps, 0.0,
                            NULL, NULL, NULL);
        if (r != GR_OK) {
#pragma omp atomic write
            erro = r;
            continue;
        }
        for (int32_t v = 1; v <= n; v++)
            if (ds[v] != INFINITY)
                ds[v] = ds[v] - potencial[s] + potencial[v];
    }
    free(ajustados);
    return erro;
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
