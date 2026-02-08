"""
Command polling and execution layer.
Polls server for pending commands and dispatches to appropriate handlers.
"""

import logging
import threading
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CommandPoller:
    """
    Polls server for pending commands and executes them.
    Commands are dispatched to registered handlers by type.
    """
    
    def __init__(self, api_client, policy_engine, poll_interval: int = 60):
        self.api_client = api_client
        self.policy_engine = policy_engine
        self.poll_interval = poll_interval
        
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
    
    def register_handler(self, command_type: str, handler: Callable):
        """
        Register a handler for a command type.
        Handler signature: handler(command_id: str, payload: dict) -> dict
        """
        self._handlers[command_type] = handler
        logger.debug(f"Registered handler for command type: {command_type}")
    
    def poll_once(self) -> int:
        """
        Poll for commands once and execute them.
        Returns number of commands processed.
        """
        if not self.policy_engine.can_execute_commands():
            logger.debug("Command execution disabled by policy")
            return 0
        
        try:
            response = self.api_client.poll_commands()
            
            if not response or 'commands' not in response:
                return 0
            
            commands = response['commands']
            processed = 0
            
            for cmd in commands:
                command_id = cmd.get('id')
                command_type = cmd.get('command_type')
                payload = cmd.get('payload', {})
                
                logger.info(f"Received command: {command_type} ({command_id})")
                
                handler = self._handlers.get(command_type)
                
                if handler:
                    try:
                        result = handler(command_id, payload)
                        self.api_client.ack_command(
                            command_id, 
                            'completed', 
                            result=result
                        )
                        logger.info(f"Command {command_id} completed")
                    except Exception as e:
                        logger.error(f"Command {command_id} failed: {e}")
                        self.api_client.ack_command(
                            command_id, 
                            'failed', 
                            error=str(e)
                        )
                else:
                    logger.warning(f"No handler for command type: {command_type}")
                    self.api_client.ack_command(
                        command_id, 
                        'failed', 
                        error=f"Unknown command type: {command_type}"
                    )
                
                processed += 1
            
            return processed
            
        except Exception as e:
            logger.error(f"Command poll error: {e}")
            return 0
    
    def _poll_loop(self):
        """Background polling loop."""
        while self._running:
            try:
                self.poll_once()
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
            
            # Sleep in small increments for quick shutdown
            elapsed = 0
            while self._running and elapsed < self.poll_interval:
                time.sleep(min(5, self.poll_interval - elapsed))
                elapsed += 5
    
    def start(self):
        """Start background polling."""
        if self._running:
            return
        
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        logger.info("Command polling started")
    
    def stop(self):
        """Stop background polling."""
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=10)
            self._poll_thread = None
        logger.info("Command polling stopped")
