"""
All-in-one OPC UA to MQTT gateway with embedded broker
"""
import logging
import asyncio
import threading
import time
import json
import signal
import sys
from amqtt.broker import Broker
import paho.mqtt.client as mqtt
from opcua_connector import OpcUaConnector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Flag to control the main loop
running = True

# MQTT broker configuration
broker_config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': '0.0.0.0:1883',
            'max_connections': 50,
        },
    },
    'sys_interval': 10,
    'auth': {
        'allow-anonymous': True,
    },
}

# MQTT client configuration
mqtt_config = {
    'broker_host': 'localhost',
    'broker_port': 1883,
    'client_id': 'opc_gateway',
    'topic_prefix': 'opcua/plc/',
    'publish_interval': 0.5
}


class MqttPublisher:
    """MQTT publisher for OPC UA values"""

    def __init__(self, config):
        self.broker_host = config['broker_host']
        self.broker_port = config['broker_port']
        self.client_id = config['client_id']
        self.topic_prefix = config['topic_prefix']
        self.publish_interval = config['publish_interval']

        # MQTT client
        self.client = mqtt.Client(self.client_id)
        self.connected = False

        # Value storage and publish thread
        self.latest_values = {}
        self.publish_thread = None
        self.keep_running = True

        # Setup callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc):
        """Called when connected to MQTT broker"""
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.connected = True
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
            self.connected = False

    def on_disconnect(self, client, userdata, rc):
        """Called when disconnected from MQTT broker"""
        logger.warning(f"Disconnected from MQTT broker with code: {rc}")
        self.connected = False

    def connect(self):
        """Connect to MQTT broker"""
        try:
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
            self.client.connect(self.broker_host, self.broker_port)

            # Start MQTT network loop in background
            self.client.loop_start()

            # Start publish thread
            self.keep_running = True
            self.publish_thread = threading.Thread(target=self._publish_loop)
            self.publish_thread.daemon = True
            self.publish_thread.start()

            return True
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        # Stop publish thread
        self.keep_running = False
        if self.publish_thread and self.publish_thread.is_alive():
            self.publish_thread.join(timeout=1.0)

        # Disconnect client
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("Disconnected from MQTT broker")
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT broker: {e}")
            finally:
                self.connected = False

    def update_value(self, name, value, unit, timestamp):
        """
        Called when a value is updated from OPC UA
        This method is used as a callback for the OPC UA connector
        """
        self.latest_values[name] = {
            "value": value,
            "unit": unit,
            "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
        }

    def _publish_loop(self):
        """Background thread that publishes values periodically"""
        while self.keep_running:
            try:
                if self.connected:
                    self._publish_values()
            except Exception as e:
                logger.error(f"Error in publish loop: {e}")

            # Wait for next publish interval
            time.sleep(self.publish_interval)

    def _publish_values(self):
        """Publish all latest values to MQTT"""
        for name, data in self.latest_values.items():
            try:
                # Create topic
                topic = f"{self.topic_prefix}{name}"

                # Create payload
                payload = json.dumps(data)

                # Publish
                self.client.publish(topic, payload, qos=1)
                logger.debug(f"Published to {topic}: {payload}")

            except Exception as e:
                logger.error(f"Error publishing {name}: {e}")


async def start_broker():
    """Start the MQTT broker"""
    broker = Broker(broker_config)
    await broker.start()
    logger.info("MQTT broker started on port 1883")
    return broker


async def shutdown_broker(broker):
    """Shutdown the MQTT broker"""
    await broker.shutdown()
    logger.info("MQTT broker stopped")


def signal_handler(sig, frame):
    """Handle Ctrl+C to stop the script gracefully"""
    global running
    logger.info("Stopping...")
    running = False


def main():
    global running

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Start MQTT broker in a separate thread using asyncio
    loop = asyncio.new_event_loop()

    def run_broker():
        asyncio.set_event_loop(loop)
        global mqtt_broker
        mqtt_broker = loop.run_until_complete(start_broker())
        loop.run_forever()

    broker_thread = threading.Thread(target=run_broker)
    broker_thread.daemon = True
    broker_thread.start()

    # Wait for broker to start
    time.sleep(1)

    # Create OPC UA connector (update with your config file path)
    opcua = OpcUaConnector('config.ini')

    # Create MQTT publisher
    mqtt = MqttPublisher(mqtt_config)

    try:
        # Connect to MQTT broker
        if not mqtt.connect():
            logger.error("Failed to connect to MQTT broker")
            return

        # Connect to OPC UA server
        if not opcua.connect():
            logger.error("Failed to connect to OPC UA server")
            mqtt.disconnect()
            return

        # Register MQTT update callback to receive OPC UA value changes
        opcua.add_value_callback(mqtt.update_value)

        # Subscribe to nodes
        if not opcua.subscribe_to_nodes():
            logger.error("Failed to subscribe to OPC UA nodes")
            opcua.disconnect()
            mqtt.disconnect()
            return

        logger.info("Bridge established between OPC UA and MQTT")
        logger.info("Press Ctrl+C to stop")

        # Main loop - keep running until interrupted
        while running:
            time.sleep(0.1)

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Cleanup
        opcua.disconnect()
        mqtt.disconnect()

        # Stop the broker
        loop.call_soon_threadsafe(lambda: asyncio.create_task(shutdown_broker(mqtt_broker)))
        loop.call_soon_threadsafe(loop.stop)
        broker_thread.join(timeout=2)


if __name__ == "__main__":
    main()