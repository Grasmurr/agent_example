import json
from confluent_kafka import Consumer, KafkaError
from pydantic import ValidationError

from models.task import TaskInput


class QueueProcessor:
    def __call__(self, *args, **kwds):
        conf = {
            'bootstrap.servers': 'localhost:9092',
            'group.id': 'ai_service',                 
            'auto.offset.reset': 'earliest'
        }
        self.consumer = Consumer(conf)
        self.consumer.subscribe(['AITasks'])
        self.is_processing = True
        self.process()
    
    def process(self):
        while self.is_processing:
            message = self.consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    print(f"Error: {message.error()}")
                    break
            try:
                message_value = json.loads(message.value().decode('utf-8'))
                message = TaskInput(**message_value)
                self.process_message(message)
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Failed to process message: {e}")

    def process_message(self, message):
        print(message)

    def stop(self):
        self.is_processing = False

if __name__ == "__main__":
    queue_processor = QueueProcessor()

    while True: pass