CC ?= gcc
CFLAGS ?= -O2 -march=native
OPCOES = -std=gnu11 -Wall -Wextra -fPIC -ffp-contract=off -fopenmp-simd
PYTHON ?= .venv/bin/python

c/libgrafos.so: c/grafos.c c/grafos.h
	$(CC) $(CFLAGS) $(OPCOES) -DGR_OPCOES='"$(CFLAGS) $(OPCOES)"' -shared -o $@ c/grafos.c -lz -lm

.PHONY: testes limpar
testes: c/libgrafos.so
	$(PYTHON) -m unittest -v test_parte2 test_motor_c

limpar:
	rm -f c/libgrafos.so
