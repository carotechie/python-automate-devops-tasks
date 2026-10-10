# 3 · Crear y proteger una cuenta de AWS

> Si solo quieres practicar, **no necesitas una cuenta de AWS**: el camino A del README
> usa LocalStack y kind en tu máquina. Esta guía es para los caminos B y C.

## Paso 1: crea la cuenta

1. Entra a [aws.amazon.com](https://aws.amazon.com) y haz clic en **Create an AWS Account**.
2. Usa un correo que revises seguido: ahí llegan las alertas de facturación.
3. Te van a pedir una tarjeta. AWS hace un cargo temporal de verificación de 1 USD.
4. Elige el plan de soporte **Basic** (gratis).

## Paso 2: activa MFA en el usuario root

El usuario root (el correo con el que creaste la cuenta) puede hacer *todo*, incluso cerrar
la cuenta. Protégelo y no lo uses para el día a día.

1. Inicia sesión como root y abre **IAM → Dashboard**.
2. En *Security recommendations*, haz clic en **Add MFA**.
3. Elige *Authenticator app* (Google Authenticator, Authy, 1Password...) o una llave física.
4. Escanea el QR e ingresa dos códigos consecutivos.

A partir de acá, usa root solo para tareas que lo exigen (por ejemplo, cambiar el plan de
soporte). Para todo lo demás, crea un usuario con IAM Identity Center
([guía 4](04-configurar-sso.md)).

## Paso 3: crea una alerta de presupuesto de 5 USD

1. Abre **Billing and Cost Management → Budgets → Create budget**.
2. Elige **Use a template → Monthly cost budget**.
3. Nombre: `alerta-5-usd`. Monto: `5`.
4. Correo: el tuyo. La plantilla te avisa cuando el gasto real llega al 85 % y al 100 %, y cuando el proyectado supera el 100 %.
5. **Create budget**.

Con la CLI (como root o con permisos de Budgets), con un ID de cuenta ficticio:

```bash
aws budgets create-budget --account-id 123456789012 \
  --budget '{"BudgetName":"alerta-5-usd","BudgetLimit":{"Amount":"5","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' \
  --notifications-with-subscribers '[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"tu-correo@example.com"}]}]'
```

## Paso 4: entiende la capa gratuita

AWS cambió su capa gratuita en julio de 2025. Las cuentas nuevas reciben créditos
(hasta 200 USD) para un plan gratuito de hasta 6 meses; las cuentas anteriores siguen con el
modelo de 12 meses. Revisa siempre la página oficial
[aws.amazon.com/free](https://aws.amazon.com/free), porque las condiciones cambian.

**Lo que normalmente no te cuesta nada para estos scripts:**

| Servicio | Por qué |
|---|---|
| IAM, IAM Identity Center, AWS Organizations | No tienen costo |
| STS (`AssumeRole`, `GetCallerIdentity`) | No tiene costo |
| Llamadas `Describe*` / `List*` de EC2 | No tienen costo |
| AWS Budgets | Los presupuestos con alertas por correo no tienen costo |

**Lo que sí cuesta (y conviene evitar al practicar):**

| Servicio | Cuidado con |
|---|---|
| EC2 | Instancias encendidas fuera de los tipos elegibles, o más horas de las incluidas |
| EBS | Volúmenes que quedan sin borrar después de terminar una instancia |
| Elastic IP | Todas las IPv4 públicas cobran por hora, incluso las que están en uso |
| NAT Gateway | Cobra por hora y por GB: es la sorpresa más común en la factura |
| **EKS** | **El plano de control cobra por hora desde que creas el cluster**, aunque no tenga nodos |

### Advertencia sobre Kubernetes

Un cluster de EKS cuesta alrededor de 0,10 USD por hora solo por el plano de control
(unos 73 USD al mes), más los nodos. **Para practicar los scripts 03 y 04 usa kind o
minikube** en tu máquina ([guía 6](06-kubernetes-local.md)): es gratis y el script se
comporta igual.

## Cómo verificar que funcionó

- En **IAM → Dashboard** ya no aparece la recomendación *Add MFA for root user*.
- En **Budgets** ves `alerta-5-usd` con estado *OK*.
- Cierras sesión como root y sigues con la [guía 4](04-configurar-sso.md) para crear tu usuario del día a día.
