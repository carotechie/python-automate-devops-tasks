# Reto 09 · Una CLI única con typer y rich

**Nivel:** Avanzado · **Tiempo estimado:** 4 h

## Contexto

Cinco scripts con cinco formas de llamarlos. Una CLI única con subcomandos es más fácil de recordar, documentar e instalar.

## Objetivo

Convertir los scripts en una CLI `caro-ops` con subcomandos: `caro-ops login`, `caro-ops find`, `caro-ops pods`, `caro-ops triage` y `caro-ops report`.

## Pistas

- `typer` arma la CLI a partir de funciones con type hints; `rich` da tablas, colores y spinners.
- No reescribas la lógica: importa las funciones que ya existen (`find_problems`, `collect`, `build_markdown`...).
- Usa `pyproject.toml` con `[project.scripts]` para que `pip install -e .` instale el comando `caro-ops`.
- Piensa la estructura de paquete (`src/caro_ops/`) y cómo mantener los tests existentes.

## Criterios de aceptación

- [ ] `pip install -e .` instala el comando `caro-ops`
- [ ] `caro-ops --help` lista los subcomandos con ayuda en español
- [ ] Al menos 4 subcomandos funcionando
- [ ] Las tablas usan `rich`
- [ ] Los exit codes de `pods` se mantienen
- [ ] Los tests existentes siguen pasando y hay tests de la CLI con `typer.testing.CliRunner`

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
