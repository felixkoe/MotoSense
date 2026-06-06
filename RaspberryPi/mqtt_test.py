# mqtt_test.py – abonniert alle motosense-Topics und gibt eingehende
# Nachrichten im Terminal aus. Nützlich zum Prüfen ob der ESP
# korrekt published

import paho.mqtt.client as mqtt

BROKER = "localhost"
TOPIC  = "motosense/#"  # # = alle Untertopics

def on_connect(client, userdata, flags, reason_code, properties):
    # subscribe() hier aufrufen, damit das Abo nach einem Reconnect
    # automatisch erneuert wird.
    print(f"Verbunden (Code {reason_code})")
    client.subscribe(TOPIC)
    print(f"Abonniert: {TOPIC}")

def on_message(client, userdata, msg):
    print(f"[{msg.topic}] {msg.payload.decode()}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, 1883, 60)
client.loop_forever()