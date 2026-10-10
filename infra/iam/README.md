# Políticas IAM de ejemplo

Todos los IDs de cuenta son ficticios. Reemplázalos por los tuyos.

| Archivo | Dónde se usa | Para qué |
|---|---|---|
| `trust-policy.json` | Rol `ReadOnly` en cada cuenta destino | Confía en la cuenta puente `111111111111` |
| `trust-policy-mfa.json` | Igual, pero exige MFA | Solo deja asumir el rol si la sesión tiene MFA |
| `hub-assume-policy.json` | Usuario o grupo en la cuenta puente | Permite `sts:AssumeRole` solo hacia los roles `ReadOnly` |

Confiar en `arn:aws:iam::111111111111:root` no significa "el usuario root": significa
"cualquier identidad de esa cuenta a la que su propia política le permita asumir el rol".
Por eso la política `hub-assume-policy.json` es la otra mitad del control.

La guía completa está en [docs/05-crear-roles-cuenta-puente.md](../../docs/05-crear-roles-cuenta-puente.md).
