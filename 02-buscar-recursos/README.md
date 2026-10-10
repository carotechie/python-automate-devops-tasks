# 02 · Buscar recursos en varias regiones

**El problema:** "¿Dónde quedó esa instancia de staging?" La consola de EC2 te muestra una
región a la vez, y la instancia siempre está en la que no revisaste.

**La automatización:** `find_ec2.py` recorre varias regiones, filtra por tags y estado y te da
una tabla o un JSON. Solo usa `ec2:DescribeInstances`.

## Uso

```bash
# Por defecto revisa us-east-1, eu-west-1 y sa-east-1
python 02-buscar-recursos/find_ec2.py --tag env=staging

# Varias condiciones: tags (AND) y estados (OR)
python 02-buscar-recursos/find_ec2.py --tag env=staging --tag team=web --state running --state stopped

# Otras regiones
python 02-buscar-recursos/find_ec2.py --regions sa-east-1,us-east-2 --tag env=prod

# JSON para encadenar con jq u otro script
python 02-buscar-recursos/find_ec2.py --tag env=staging --output json | jq '.[].instance_id'

# Con un perfil
python 02-buscar-recursos/find_ec2.py --profile staging-readonly --tag env=staging
```

## Contra el laboratorio local

```bash
make lab-up
source lab/lab.env
python 02-buscar-recursos/find_ec2.py --endpoint-url http://localhost:4566 --tag env=staging
```

(`lab/lab.env` ya define `AWS_ENDPOINT_URL`, así que `--endpoint-url` es opcional.)

Salida real contra un emulador local con los datos de `lab/seed_localstack.py`:

```text
| Región    | ID                  | Nombre            | Tipo     | Estado   | IP privada     | Creada                    |
|-----------|---------------------|-------------------|----------|----------|----------------|---------------------------|
| eu-west-1 | i-7b056af9955d324b1 | api-staging-01    | t3.small | stopped  | 10.162.164.147 | 2026-10-10T15:29:21+00:00 |
| sa-east-1 | i-571d085dba638a5b8 | worker-staging-01 | t3.micro | running  | 10.226.164.212 | 2026-10-10T15:29:21+00:00 |
| us-east-1 | i-d24bdb7df17f6c1bd | web-staging-01    | t3.micro | running  | 10.127.113.202 | 2026-10-10T15:29:21+00:00 |

3 instancia(s) en 3 región(es).
```

## Detalles técnicos

- **Paginadores:** `describe_instances` devuelve como mucho 1000 resultados por página. El
  paginador de boto3 pide las siguientes páginas por ti; sin él, en cuentas grandes te faltan instancias.
- **Filtros del lado del servidor:** los tags y el estado se mandan como `Filters`, así AWS
  devuelve solo lo que necesitas.
- **Permisos mínimos:** `ec2:DescribeInstances`. Funciona con la política `ReadOnlyAccess`.

## Ideas para extenderlo

- Agregar `--all-regions` usando `ec2.describe_regions()`.
- Buscar también volúmenes EBS sin adjuntar: es el [reto bonus 01](../bonus/retos/01-volumenes-ebs-sin-adjuntar.md).
