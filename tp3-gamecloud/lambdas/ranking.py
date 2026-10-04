import json
import os
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("TABLE_NAME")
table = dynamodb.Table(TABLE_NAME)

# Helper para serializar tipos Decimal de DynamoDB
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    try:
        params = event.get("queryStringParameters") or {}
        juego_filtro = params.get("juego")

        if juego_filtro:
            response = table.query(
                KeyConditionExpression=Key("juego").eq(juego_filtro)
            )
            items = response.get("Items", [])
            items_ordenados = sorted(
                items, key=lambda x: int(x["puntaje"]), reverse=True
            )[:10]
            resultado = {juego_filtro: items_ordenados}
        else:
            response = table.scan()
            items = response.get("Items", [])
            juegos_dict = {}
            for item in items:
                j = item["juego"]
                juegos_dict.setdefault(j, []).append(item)

            resultado = {}
            for juego, lista in juegos_dict.items():
                ordenados = sorted(
                    lista, key=lambda x: int(x["puntaje"]), reverse=True
                )[:10]
                resultado[juego] = ordenados

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(resultado, cls=DecimalEncoder),
        }
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
