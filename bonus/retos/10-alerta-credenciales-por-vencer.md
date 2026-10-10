# Reto 10 · Alerta de credenciales a punto de vencer

**Nivel:** Avanzado · **Tiempo estimado:** 2 h

## Contexto

Nada interrumpe más que un `ExpiredToken` en medio de un comando largo. Los scripts del módulo 01 guardan la expiración de cada perfil en `x_security_token_expires`.

## Objetivo

Leer la expiración de los perfiles en `~/.aws/credentials` y avisar 5 minutos antes de que venzan.

## Pistas

- `configparser` lee el archivo de credenciales; respeta `AWS_SHARED_CREDENTIALS_FILE`.
- La expiración está en formato ISO 8601 con zona horaria.
- Para avisar: notificación de escritorio (`osascript` en macOS, `notify-send` en Linux, `plyer` multiplataforma) o solo un mensaje en la terminal.
- Piensa si conviene un proceso que queda corriendo o algo que se agenda con cron/launchd.

## Criterios de aceptación

- [ ] Lista los perfiles con expiración, cuánto les queda y cuáles ya vencieron
- [ ] Avisa cuando a un perfil le quedan 5 minutos o menos (configurable)
- [ ] No muestra ni loguea las credenciales, solo nombres de perfil y fechas
- [ ] Ignora perfiles sin expiración
- [ ] Tiene tests con un archivo de credenciales temporal y una fecha fija

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
