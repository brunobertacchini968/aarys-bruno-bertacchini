import json
import os
import boto3

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("TABLE_NAME")
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
  for record in event.get("Records", []):
    try:
      payload = json.loads(record["body"])
      jugador = payload["jugador"]
      juego = payload["juego"]
      nuevo_puntaje = int(payload["puntaje"])

      # Consultar puntaje actual en DynamoDB (Clave de partición: juego, ordenamiento: jugador)
      response = table.get_item(Key={"juego": juego, "jugador": jugador})

      actualizar = False
      if "Item" in response:
        puntaje_actual = int(response["Item"]["puntaje"])
        if nuevo_puntaje > puntaje_actual:
          actualizar = True
      else:
        actualizar = True  # Primer registro del jugador en este juego

      if actualizar:
        table.put_item(
            Item={"juego": juego, "jugador": jugador, "puntaje": nuevo_puntaje}
        )
        print(f"Nuevo récord guardado: {jugador} en {juego} con {nuevo_puntaje}")
      else:
        print(
            f"El puntaje {nuevo_puntaje} no supera el récord existente para"
            f" {jugador}"
        )

    except Exception as e:
      print(f"Error procesando mensaje SQS: {str(e)}")
      raise e  # Forzar reintento o envío a DLQ si se agotan los intentos
