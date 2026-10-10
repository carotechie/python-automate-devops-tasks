# Reto 05 · Enviar el resumen del incidente a Slack o Teams

**Nivel:** Intermedio · **Tiempo estimado:** 1 h

## Contexto

`04-triage-incidentes/triage.py` genera un Markdown. El siguiente paso natural es que llegue solo al canal del incidente.

## Objetivo

Agregar una opción para enviar un resumen corto del incidente a un webhook de Slack o Teams.

## Pistas

- Slack: *Incoming Webhooks* reciben un POST con JSON. Mira el formato *Block Kit*.
- Teams: los *Workflows* (Power Automate) aceptan webhooks con *Adaptive Cards*.
- Puedes usar `urllib.request` de la librería estándar, sin dependencias nuevas.
- La URL del webhook es un secreto: léela de una variable de entorno, nunca de un flag ni del código.
- No mandes el Markdown entero: arma un resumen (estado, razón principal, último evento) y un link o adjunto al archivo.

## Criterios de aceptación

- [ ] La URL se lee de `SLACK_WEBHOOK_URL` o `TEAMS_WEBHOOK_URL`
- [ ] Si la variable no existe, el script funciona igual que antes
- [ ] El mensaje incluye app, namespace, réplicas listas/deseadas y la razón principal
- [ ] Maneja errores HTTP sin perder el archivo local
- [ ] Tiene un test que mockea la llamada HTTP y verifica el payload
- [ ] La URL del webhook nunca aparece en logs ni en la salida

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
