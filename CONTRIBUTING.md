# Cómo contribuir

¡Gracias por querer sumar! Este repo acompaña una charla para PyLadies, así que la prioridad
es que sea **claro para quien empieza** sin perder el nivel técnico.

## Formas de contribuir

- **Compartir la solución de un reto:** abre un issue con la plantilla *Solución de un reto bonus*.
- **Reportar un bug:** usa la plantilla *Reporte de bug* con el comando exacto y el error.
- **Mejorar la documentación:** una guía que no funcionó en tu sistema operativo es un bug de documentación.
- **Proponer un reto nuevo:** abre un issue contando el problema que resuelve.

## Preparar el entorno

```bash
git clone https://github.com/carotechie/python-automatiza-devops.git
cd python-automatiza-devops
make setup
source .venv/bin/activate
pip install pre-commit && pre-commit install
```

## Antes de abrir un PR

```bash
make lint   # ruff check
make test   # pytest
```

El CI corre lo mismo en Python 3.10, 3.11 y 3.12.

## Reglas del código

- **Solo lectura.** Ningún script modifica ni borra recursos de AWS o Kubernetes.
- **Testeable.** Funciones chicas y un `main(argv=None)` que devuelve el exit code.
- **Tests sin cuenta real.** `moto` para EC2/STS/IAM/S3, `botocore.stub.Stubber` para APIs que moto
  no emula (como SSO) y mocks para Kubernetes.
- **Idioma.** Documentación, comentarios y mensajes para la persona en español neutro (sin voseo).
  Nombres de variables, funciones, archivos y mensajes de log en inglés.
- **Datos ficticios.** IDs de cuenta como `111111111111` o `123456789012`, URLs con `example.com`
  o `d-1234567890`. Nunca nombres de empresas, clientes ni datos reales.
- **Sin secretos.** `pre-commit` con `detect-secrets` te avisa antes del commit.

## Estilo de commits

Mensajes cortos en imperativo, en español o inglés: `Agrega reto de Elastic IPs`, `Fix pods_check exit code`.
