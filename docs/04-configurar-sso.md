# 4 · Configurar IAM Identity Center (SSO)

IAM Identity Center (antes "AWS SSO") te da **un solo login** para entrar a todas tus cuentas
con credenciales temporales. Es lo que usa `01-acceso-multicuenta/sso_switch.py`.

Todo esto no tiene costo. Los IDs y URLs de los ejemplos son ficticios.

## Paso 1: activa IAM Identity Center

1. Inicia sesión en la consola (como root solo esta vez, o con un usuario administrador).
2. Elige la región donde vas a administrar Identity Center (por ejemplo `us-east-1`).
   Anótala: es tu `SSO_REGION`.
3. Busca **IAM Identity Center** y haz clic en **Enable**.
4. Te va a ofrecer **activar AWS Organizations**: acepta. Identity Center necesita una
   organización, aunque tengas una sola cuenta. Tu cuenta pasa a ser la *management account*.

## Paso 2: crea un usuario y un grupo

1. **Users → Add user**. Usuario: `caro`, tu correo, nombre y apellido.
2. Te llega un correo para definir la contraseña. Actívala y **configura MFA** cuando te lo pida.
3. **Groups → Create group**. Nombre: `devops`. Agrega a tu usuario.

Trabajar con grupos en lugar de usuarios sueltos hace que dar o quitar accesos sea un solo cambio.

## Paso 3: crea los permission sets

Un *permission set* es una plantilla de permisos que se convierte en un rol dentro de cada
cuenta donde lo asignas.

1. **Permission sets → Create permission set → Predefined permission set**.
2. Elige `ReadOnlyAccess`. En **Session duration** elige, por ejemplo, `4 hours`.
3. Repite con `AdministratorAccess` y una duración corta, por ejemplo `1 hour`.

### ¿Dónde se configura la duración de la sesión?

Hay **dos duraciones distintas** y es fácil confundirlas:

| Qué | Dónde | Rango | Qué controla |
|---|---|---|---|
| Duración de la sesión del permission set | *Permission sets → (el set) → Edit → Session duration* | 1 a 12 h (por defecto 1 h) | Cuánto duran las credenciales de AWS que obtienes |
| Duración de la sesión del portal | *Settings → Authentication → Session settings* | Hasta varios días | Cuánto tiempo puedes seguir sin volver a hacer login |

`sso.get_role_credentials` **no recibe un parámetro de duración**: las credenciales duran lo
que diga el permission set. Si quieres sesiones más largas, cambia el permission set; el
script no puede pedir más.

## Paso 4: asigna el grupo a la cuenta

1. **AWS accounts** → marca tu cuenta → **Assign users or groups**.
2. Pestaña **Groups** → `devops` → **Next**.
3. Marca `ReadOnlyAccess` y `AdministratorAccess` → **Next** → **Submit**.

## Paso 5: copia la AWS access portal URL

En el **Dashboard** de Identity Center, en *Settings summary*, copia la **AWS access portal URL**.
Tiene esta forma:

```text
https://d-1234567890.awsapps.com/start
```

Esa URL es tu `SSO_START_URL`. Guárdala en tu `.env` (copia `.env.example`).

## Paso 6: configura la CLI

```bash
aws configure sso
```

Responde:

```text
SSO session name (Recommended): lab
SSO start URL [None]: https://d-1234567890.awsapps.com/start
SSO region [None]: us-east-1
SSO registration scopes [sso:account:access]:
```

Se abre el navegador para autorizar. Después elige la cuenta y el rol `ReadOnlyAccess`, y:

```text
Default client Region [None]: us-east-1
CLI default output format [None]: json
Profile name [ReadOnlyAccess-123456789012]: lab-readonly
```

Eso deja algo así en `~/.aws/config`:

```ini
[profile lab-readonly]
sso_session = lab
sso_account_id = 123456789012
sso_role_name = ReadOnlyAccess
region = us-east-1

[sso-session lab]
sso_start_url = https://d-1234567890.awsapps.com/start
sso_region = us-east-1
sso_registration_scopes = sso:account:access
```

## Paso 7: inicia sesión

```bash
aws sso login --profile lab-readonly
```

Esto deja un token en `~/.aws/sso/cache/`. `sso_switch.py` lo reutiliza: no te pide login de
nuevo mientras el token esté vigente. El token de acceso dura poco (en general 1 h) y la CLI lo
renueva sola cuando usas un comando `aws`; si el script te dice que no hay token vigente,
vuelve a ejecutar `aws sso login`.

## Cómo verificar que funcionó

```bash
aws sts get-caller-identity --profile lab-readonly
```

Tienes que ver un ARN como:

```text
arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_ReadOnlyAccess_abc123/caro
```

Y después, el script:

```bash
python 01-acceso-multicuenta/sso_switch.py --start-url https://d-1234567890.awsapps.com/start
```
