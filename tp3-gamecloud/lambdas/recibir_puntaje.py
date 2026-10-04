import json
import os
import boto3

sqs = boto3.client("sqs")
QUEUE_URL = os.environ.get("QUEUE_URL")


def lambda_handler(event, context):
  try:
    # Manejar si el evento viene de API Gateway (HTTP API payload v2.0)
    body = json.loads(event.get("body", "{}"))

    jugador = body.get("jugador")
    juego = body.get("juego")
    puntaje = body.get("puntaje")

    # Validaciones obligatorias
    if (
        not jugador
        or not juego
        or not isinstance(puntaje, int)
        or puntaje < 0
    ):
      return {
          "statusCode": 400,
          "body": json.dumps({"error": "Datos inválidos o incompletos"}),
      }

    # Enviar mensaje a la cola SQS
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(
            {"jugador": jugador, "juego": juego, "puntaje": puntaje}
        ),
    )

    return {
        "statusCode": 202,
        "body": json.dumps(
            {"message": "Puntaje recibido y encolado exitosamente"}
        ),
    }
  except Exception as e:
    return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
