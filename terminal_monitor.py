"""
Simple terminal-based monitor for OPC UA values
"""
import logging
import time
import datetime
import argparse
import os
import sys
from opcua_connector import OpcUaConnector

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)


class TerminalMonitor:
    """
    Terminal-based monitor for OPC UA values
    """

    def __init__(self, config_file='config.ini'):
        """Initialize terminal monitor"""
        self.config_file = config_file
        self.connector = OpcUaConnector(config_file)
        self.running = False

        # Add value callback
        self.connector.add_value_callback(self.on_value_change)

        # Keep track of displayed values
        self.displayed_values = {}

    def on_value_change(self, name, value, unit, timestamp):
        """Called when a value changes"""
        self.displayed_values[name] = {
            "value": value,
            "unit": unit,
            "timestamp": timestamp
        }

        # Update terminal display
        self._update_display()

    def _update_display(self):
        """Update the terminal display with current values"""
        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')

        # Print header
        print("=" * 50)
        print(f" OPC UA Terminal Monitor - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        print()

        # Print each value
        for name, data in self.displayed_values.items():
            value = data["value"]
            unit = data["unit"]
            timestamp = data["timestamp"]

            # Format timestamp
            if isinstance(timestamp, datetime.datetime):
                time_str = timestamp.strftime("%H:%M:%S")
            else:
                time_str = str(timestamp)

            # Format unit
            unit_str = f" {unit}" if unit else ""

            print(f"[{time_str}] {name}: {value}{unit_str}")

        print("\nPress Ctrl+C to exit")

    def start(self):
        """Start monitoring"""
        try:
            # Connect to OPC UA server
            if not self.connector.connect():
                logger.error("Failed to connect to OPC UA server")
                return False

            # Subscribe to nodes
            if not self.connector.subscribe_to_nodes():
                logger.error("Failed to subscribe to nodes")
                self.connector.disconnect()
                return False

            # Set running flag
            self.running = True

            # Display initial message
            self._update_display()

            # Keep running until Ctrl+C
            try:
                while self.running:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")

            return True
        except Exception as e:
            logger.error(f"Error starting monitor: {e}")
            return False
        finally:
            # Ensure we disconnect
            if self.connector.connected:
                self.connector.disconnect()

    def stop(self):
        """Stop monitoring"""
        self.running = False


def main():
    """Main entry point for terminal monitor"""
    parser = argparse.ArgumentParser(description="OPC UA Terminal Monitor")
    parser.add_argument("--config", "-c", default="config.ini", help="Path to configuration file")
    args = parser.parse_args()

    monitor = TerminalMonitor(args.config)
    monitor.start()


if __name__ == "__main__":
    main()