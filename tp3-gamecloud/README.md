# TP3 — GameCloud: Aplicaciones en la Nube

Implementación de una arquitectura serverless para el ranking online de puntajes de **GameCloud**, utilizando servicios de AWS sobre **MiniStack**, un emulador local de AWS.

## Descripción

GameCloud necesita publicar un ranking online para sus juegos, permitiendo:

* Consultar los mejores puntajes.
* Registrar nuevos puntajes.
* Procesar los puntajes de forma asíncrona.
* Mantener únicamente el mejor puntaje de cada jugador por juego.
* Soportar picos de tráfico mediante una cola de mensajes.
* Separar los mensajes que no pueden procesarse mediante una Dead Letter Queue (DLQ).

La implementación se realiza localmente mediante MiniStack, utilizando la misma interfaz de línea de comandos (`AWS CLI`) que se utilizaría para trabajar con AWS.

---

## Arquitectura

```text
                              ┌─────────────────┐
                              │     Jugador     │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │   CloudFront    │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │   S3 - Web      │
                              │  index.html     │
                              └─────────────────┘


Jugador
   │
   ├──────── GET /ranking ────────┐
   │                              ▼
   │                       ┌───────────────┐
   │                       │ API Gateway   │
   │                       │ gamecloud-api │
   │                       └───────┬───────┘
   │                               │
   │                               ▼
   │                       ┌───────────────┐
   │                       │ Lambda        │
   │                       │ ranking       │
   │                       └───────┬───────┘
   │                               │
   │                               ▼
   │                       ┌───────────────┐
   │                       │  DynamoDB     │
   │                       │   Puntajes    │
   │                       └───────────────┘
   │
   │
   └──────── POST /scores ────────┐
                                  ▼
                           ┌───────────────┐
                           │ API Gateway   │
                           └───────┬───────┘
                                   │
                                   ▼
                           ┌───────────────┐
                           │ Lambda        │
                           │ recibir_      │
                           │ puntaje       │
                           └───────┬───────┘
                                   │
                                   ▼
                           ┌───────────────┐
                           │     SQS       │
                           │   puntajes    │
                           └───────┬───────┘
                                   │
                                   ▼
                           ┌───────────────┐
                           │ Lambda        │
                           │ procesar_     │
                           │ puntaje       │
                           └───────┬───────┘
                                   │
                                   ▼
                           ┌───────────────┐
                           │  DynamoDB     │
                           │   Puntajes    │
                           └───────────────┘

                                   │
                          3 intentos fallidos
                                   ▼
                           ┌───────────────┐
                           │  puntajes-dlq │
                           │     (DLQ)     │
                           └───────────────┘
```

### Componentes

| Servicio    | Recurso                 | Responsabilidad                         |
| ----------- | ----------------------- | --------------------------------------- |
| S3          | `gamecloud-web`         | Almacenar el frontend estático          |
| CloudFront  | Distribución GameCloud  | Distribuir el contenido del frontend    |
| API Gateway | `gamecloud-api`         | Exponer la API HTTP                     |
| Lambda      | `ranking`               | Consultar el ranking                    |
| Lambda      | `recibir_puntaje`       | Validar y encolar puntajes              |
| Lambda      | `procesar_puntaje`      | Procesar mensajes y actualizar DynamoDB |
| SQS         | `puntajes`              | Cola principal de puntajes              |
| SQS         | `puntajes-dlq`          | Mensajes que fallaron repetidamente     |
| DynamoDB    | `Puntajes`              | Persistir los mejores puntajes          |
| IAM         | `gamecloud-lambda-role` | Permisos de las funciones Lambda        |

---

# Estructura del proyecto

```text
tp3-gamecloud/
│
├── README.md
├── docker-compose.yml
│
├── iam/
│   ├── trust-lambda.json
│   └── politica-lambdas.json
│
├── lambdas/
│   ├── ranking.py
│   ├── recibir_puntaje.py
│   └── procesar_puntaje.py
│
├── scripts/
│   ├── cloudfront.json
│
└── web/
    ├── index.html
    └── config.js
```

---

# Requisitos

Para ejecutar el proyecto se necesitan:

* Docker
* Docker Compose
* AWS CLI
* Bash
* `curl`
* `zip`

No es necesaria una cuenta real de AWS.

La práctica utiliza MiniStack como emulador local de los servicios de AWS.

---

# 0. Preparación del entorno

## Levantar MiniStack

```bash
docker compose up -d
```

Verificar el contenedor:

```bash
docker ps
```

El servicio debe estar disponible en:

```text
http://localhost:4566
```

## Configurar AWS CLI

Configurar credenciales ficticias:

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
```

Crear el alias utilizado durante la práctica:

```bash
alias awsl='aws --endpoint-url=http://localhost:4566'
```

Verificar la conexión:

```bash
awsl s3 ls
```

---

# 1. Frontend estático en S3

## Crear bucket

```bash
awsl s3 mb s3://gamecloud-web
```

Verificar:

```bash
awsl s3 ls
```

## Habilitar Static Website Hosting

```bash
awsl s3 website s3://gamecloud-web \
    --index-document index.html
```

Verificar:

```bash
awsl s3api get-bucket-website \
    --bucket gamecloud-web
```

## Subir frontend

```bash
awsl s3 cp web/index.html \
    s3://gamecloud-web/index.html
```

Verificar:

```bash
awsl s3 ls s3://gamecloud-web
```

## Acceder al sitio

```text
http://localhost:4566/gamecloud-web/index.html
```

> MiniStack permite crear la distribución de CloudFront mediante API, pero no sirve el contenido a través de ella. Por este motivo, la prueba del frontend se realiza directamente mediante la URL de S3.

---

# 2. CloudFront

Crear la distribución utilizando el bucket `gamecloud-web` como origen.

La distribución se utiliza para representar la arquitectura final:

```text
Jugador → CloudFront → S3
```

En un entorno AWS real, CloudFront permite distribuir el contenido mediante una CDN, reduciendo la latencia y utilizando caché para acercar los recursos a los usuarios.

Para esta práctica, la existencia de la distribución se verifica mediante la API de MiniStack.

```bash
awsl cloudfront list-distributions
```

---

# 3. DynamoDB

La tabla utilizada para almacenar los puntajes se llama:

```text
Puntajes
```

## Estructura

| Atributo  | Tipo   | Clave         |
| --------- | ------ | ------------- |
| `juego`   | String | Partition Key |
| `jugador` | String | Sort Key      |
| `puntaje` | Number | Atributo      |

## Crear tabla

```bash
awsl dynamodb create-table \
    --table-name Puntajes \
    --attribute-definitions \
        AttributeName=juego,AttributeType=S \
        AttributeName=jugador,AttributeType=S \
    --key-schema \
        AttributeName=juego,KeyType=HASH \
        AttributeName=jugador,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST
```

## Verificar estado

```bash
awsl dynamodb describe-table \
    --table-name Puntajes \
    --query 'Table.TableStatus'
```

Debe devolver:

```text
"ACTIVE"
```

## Consultar registros

```bash
awsl dynamodb scan \
    --table-name Puntajes
```

La clave compuesta `(juego, jugador)` garantiza que cada jugador tenga un único registro por juego.

Por ejemplo:

```text
doom + ana
```

identifica un único elemento de la tabla.

Si `ana` obtiene un puntaje mayor en `doom`, se actualiza el registro existente en lugar de crear uno nuevo.

---

# 4. SQS

La arquitectura utiliza dos colas:

```text
puntajes
    │
    │ 3 intentos fallidos
    ▼
puntajes-dlq
```

## Dead Letter Queue

Crear:

```bash
awsl sqs create-queue \
    --queue-name puntajes-dlq
```

Obtener URL:

```bash
DLQ_URL=$(awsl sqs get-queue-url \
    --queue-name puntajes-dlq \
    --query 'QueueUrl' \
    --output text)
```

Obtener ARN:

```bash
DLQ_ARN=$(awsl sqs get-queue-attributes \
    --queue-url "$DLQ_URL" \
    --attribute-names QueueArn \
    --query 'Attributes.QueueArn' \
    --output text)
```

## Cola principal

Crear `puntajes` con un visibility timeout de 30 segundos:

```bash
awsl sqs create-queue \
    --queue-name puntajes \
    --attributes VisibilityTimeout=30
```

Obtener URL:

```bash
QUEUE_URL=$(awsl sqs get-queue-url \
    --queue-name puntajes \
    --query 'QueueUrl' \
    --output text)
```

## Redrive Policy

Crear la política:

```bash
cat > /tmp/redrive-policy.json <<EOF
{
  "deadLetterTargetArn": "$DLQ_ARN",
  "maxReceiveCount": "3"
}
EOF
```

Aplicarla:

```bash
awsl sqs set-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attributes RedrivePolicy="$(cat /tmp/redrive-policy.json)"
```

Verificar:

```bash
awsl sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attribute-names VisibilityTimeout RedrivePolicy
```

---

# 5. IAM

Las funciones Lambda utilizan el rol:

```text
gamecloud-lambda-role
```

El rol debe permitir que Lambda lo asuma mediante una trust policy.

Los permisos deben seguir el principio de **mínimo privilegio**, otorgando únicamente las operaciones necesarias sobre:

* DynamoDB
* SQS
* CloudWatch Logs

La trust policy se encuentra en:

```text
iam/trust-lambda.json
```

La política de permisos se encuentra en:

```text
iam/politica-lambdas.json
```

---

# 6. AWS Lambda

La aplicación utiliza tres funciones Lambda.

## `ranking`

Responsabilidad:

```text
GET /ranking
```

Consulta DynamoDB y devuelve los mejores 10 puntajes de cada juego.

También acepta:

```text
GET /ranking?juego=doom
```

En ese caso devuelve únicamente el ranking del juego solicitado.

---

## `recibir_puntaje`

Responsabilidad:

```text
POST /scores
```

Recibe:

```json
{
  "jugador": "ana",
  "juego": "doom",
  "puntaje": 9800
}
```

Valida:

* existencia de `jugador`
* existencia de `juego`
* que `puntaje` sea entero

Si los datos son válidos:

```text
HTTP 202 Accepted
```

y el mensaje se envía a SQS.

**Esta función no escribe directamente en DynamoDB.**

Si los datos son inválidos:

```text
HTTP 400 Bad Request
```

---

## `procesar_puntaje`

Esta función es disparada por la cola SQS.

Su flujo es:

```text
SQS
 │
 ▼
procesar_puntaje
 │
 ├── leer mensaje
 │
 ├── validar datos
 │
 ├── consultar DynamoDB
 │
 ├── comparar puntajes
 │
 └── actualizar únicamente si es mayor
```

Ejemplo:

```text
Puntaje existente: 9800
Nuevo puntaje:      8500
                     ↓
                  ignorar
```

Mientras que:

```text
Puntaje existente: 9800
Nuevo puntaje:     12000
                     ↓
                 actualizar
```

---

# 7. Event Source Mapping

La función:

```text
procesar_puntaje
```

se conecta a:

```text
puntajes
```

mediante un event source mapping.

El flujo completo queda:

```text
POST /scores
     │
     ▼
API Gateway
     │
     ▼
recibir_puntaje
     │
     ▼
SQS puntajes
     │
     ▼
procesar_puntaje
     │
     ▼
DynamoDB
```

Si el procesamiento falla repetidamente:

```text
puntajes
   │
   │ 3 fallos
   ▼
puntajes-dlq
```

---

# 8. API Gateway

Crear una HTTP API llamada:

```text
gamecloud-api
```

## Rutas

### GET `/ranking`

Integración:

```text
Lambda ranking
```

### POST `/scores`

Integración:

```text
Lambda recibir_puntaje
```

Ambas integraciones utilizan:

```text
AWS_PROXY
```

## CORS

Se habilita CORS para:

```text
GET
POST
```

## Stage

Se utiliza:

```text
$default
```

con:

```text
auto-deploy = true
```

## Throttling

```text
Rate: 100 requests/second
Burst: 200
```

---

# 9. Configuración del frontend

El frontend obtiene la URL de la API desde:

```text
web/config.js
```

Contenido:

```javascript
window.GAMECLOUD_API = "http://<API_ID>.execute-api.localhost:4566";
```

Reemplazar:

```text
<API_ID>
```

por el identificador real de `gamecloud-api`.

Luego subir:

```bash
awsl s3 cp web/config.js \
    s3://gamecloud-web/config.js
```

El frontend quedará conectado con:

```text
S3 → API Gateway → Lambda
```

---

# 10. Pruebas

## 10.1 Puntaje válido

Ejemplo:

```bash
curl -X POST \
    http://<API_ID>.execute-api.localhost:4566/scores \
    -H 'Content-Type: application/json' \
    -d '{"jugador":"ana","juego":"doom","puntaje":9800}'
```

Resultado esperado:

```text
HTTP 202 Accepted
```

Se deben enviar al menos **5 puntajes válidos** de distintos jugadores y juegos.

---

## 10.2 Puntaje inválido

Enviar un juego inexistente o datos incorrectos.

Resultado esperado:

```text
HTTP 400 Bad Request
```

---

## 10.3 Puntaje menor

Supongamos:

```text
ana / doom / 9800
```

Ya existe en DynamoDB.

Enviar:

```text
ana / doom / 5000
```

El ranking no debe cambiar.

---

## 10.4 Consultar ranking

```bash
curl \
    http://<API_ID>.execute-api.localhost:4566/ranking
```

También:

```bash
curl \
    "http://<API_ID>.execute-api.localhost:4566/ranking?juego=doom"
```

---

## 10.5 Simular un pico

Enviar 50 puntajes en paralelo.

Ejemplo:

```bash
for i in $(seq 1 50); do
    curl -s -X POST \
        http://<API_ID>.execute-api.localhost:4566/scores \
        -H 'Content-Type: application/json' \
        -d "{\"jugador\":\"jugador$i\",\"juego\":\"doom\",\"puntaje\":$((RANDOM % 10000))}" &
done

wait
```

Verificar el estado de la cola:

```bash
awsl sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attribute-names ApproximateNumberOfMessages
```

Registrar el estado:

1. Durante el pico.
2. Una vez procesados los mensajes.

---

## 10.6 Probar la DLQ

Enviar directamente un mensaje inválido:

```bash
awsl sqs send-message \
    --queue-url "$QUEUE_URL" \
    --message-body 'esto no es JSON'
```

El mensaje debería ser procesado por `procesar_puntaje`, fallar y, después de los intentos configurados, terminar en:

```text
puntajes-dlq
```

Consultar la DLQ:

```bash
awsl sqs receive-message \
    --queue-url "$DLQ_URL"
```

---

# 11. CloudWatch Logs

Los logs de `procesar_puntaje` se pueden consultar mediante:

```bash
awsl logs filter-log-events \
    --log-group-name /aws/lambda/procesar_puntaje
```

Estos logs permiten verificar:

* recepción de mensajes;
* procesamiento;
* errores;
* actualización de DynamoDB;
* mensajes inválidos.
