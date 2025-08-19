import asyncio
from azure.servicebus.aio import ServiceBusClient
# pip install azure-servicebus

CONN_STR = "<PrimaryConnectionString>"
#QUEUE = "<QUEUE_NAME>"

# For topics/subscriptions, you would use:
TOPIC = "labtopic"
SUBSCRIPTION = "labsub"

async def receive():
    async with ServiceBusClient.from_connection_string(CONN_STR) as client:
        # For a queue receiver:
        #async with client.get_queue_receiver(queue_name=QUEUE, max_wait_time=5) as receiver:
        #    msgs = await receiver.receive_messages(max_wait_time=5, max_message_count=20)
        #    for msg in msgs:
        #        print("Received:", msg)
        #        await receiver.complete_message(msg)

        # For a topic/subscription receiver (commented out):
        async with client.get_subscription_receiver(topic_name=TOPIC, subscription_name=SUBSCRIPTION, max_wait_time=5) as receiver:
            msgs = await receiver.receive_messages(max_wait_time=5, max_message_count=20)
            for msg in msgs:
                print("Received:", msg)
                await receiver.complete_message(msg)

asyncio.run(receive())
print("Done receiving messages")
