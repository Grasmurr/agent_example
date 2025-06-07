import time
import os
import logging
from multiprocessing.managers import ListProxy
import redis

# Import TGAPI from the current directory
from components.tools.tg_api_service import TGAPI

class TGTool(TGAPI):
    def __init__(self, tg_messages: ListProxy, agent=None):
        """
        Initialize TGTool with messaging capabilities.
        
        Args:
            tg_messages: Managed list for storing messages
            agent: Reference to the agent instance (optional)
        """
        # Initialize parent TGAPI class
        super().__init__(os.getenv('TG_BOT_TOKEN'))

        self.TG_CHAT_ID = int(os.getenv('TG_CHAT_ID', 0))
        self.TG_BASE_THREAD_ID = int(os.getenv('TG_BASE_THREAD_ID', 1))
        self.tg_messages = tg_messages
        self.agent = agent  # Store reference to agent

        # Initialize Redis client
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True
        )
        self.redis_chat_key = "agent:chat_messages"

    def send_telegram_message(self, text: str) -> str:
        """
        Sends a message to the user using Telegram without HTML formatting.
        
        Args:
            text: Text content to send
            
        Returns:
            Result of the operation
        """
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        base_message = f"\nApollinaria: {text}"

        try:
            existing_messages = self.redis_client.lrange(self.redis_chat_key, 0, 99)
            for msg in existing_messages:
                if msg.startswith(base_message):
                    # Additional logging for duplicate detection
                    logging.warning(f"Duplicate message detected: {text[:50]}...")
                    return "This message has already been sent!"
        except Exception as e:
            logging.error(f"Failed to read messages from Redis: {e}")

        message = f"{base_message} (delivered and read {timestamp})"

        try:
            self.redis_client.lpush(self.redis_chat_key, message)
            self.redis_client.ltrim(self.redis_chat_key, 0, 99)  # Keep only the last 100 messages
        except Exception as e:
            logging.error(f"Failed to add message to Redis chat: {e}")

        self.tg_messages.append(message)
        
        result = {}
        if int(self.TG_BASE_THREAD_ID) == 1:
            result = super().send_msg(
                chat_id=self.TG_CHAT_ID,
                text=f'[{os.getenv("MACHINE_NAME") or "unknown machine"}]\n\n{text}',
                parse_mode='HTML'
            )
            return f"response: {result}"
            # return f"Message sent successfully"
        
        try:
            result = super().send_msg(
                chat_id=self.TG_CHAT_ID,
                text=f'[{os.getenv("MACHINE_NAME") or "unknown machine"}]\n\n{text}',
                message_thread_id=self.TG_BASE_THREAD_ID,
                parse_mode='HTML'
            )
        except Exception as e:
            # Fallback without parse_mode if HTML parsing fails
            result = super().send_msg(
                chat_id=self.TG_CHAT_ID,
                text=f'[{os.getenv("MACHINE_NAME") or "unknown machine"}]\n\n{text}',
                message_thread_id=self.TG_BASE_THREAD_ID
            )
            return f"response: {result}"
        # return "Message sent successfully"

    def create_forum_topic(self, chat_id, name, icon_color=None, icon_custom_emoji_id=None):
        """
        Creates a new forum topic (thread) in a supergroup.
        
        Args:
            chat_id: ID of the supergroup
            name: Name of the forum topic
            icon_color: Color of the topic icon (optional)
            icon_custom_emoji_id: Custom emoji ID for the topic icon (optional)
            
        Returns:
            Response from Telegram API or None on failure
        """
        params = {
            'chat_id': chat_id,
            'name': name
        }
        
        if icon_color:
            params['icon_color'] = icon_color
        
        if icon_custom_emoji_id:
            params['icon_custom_emoji_id'] = icon_custom_emoji_id
        
        try:
            return super().method('createForumTopic', params)
        except Exception as e:
            logging.error(f"Error creating forum topic: {e}")
            return None
    
    def process_command(self, message_text: str, message_obj: dict) -> bool:
        """
        Processes special bot commands.
        
        Args:
            message_text: Text content of the message
            message_obj: Message object from Telegram
            
        Returns:
            True if command was processed, False otherwise
        """
        if message_text.startswith('/set_mode'):
            return self._handle_set_mode_command(message_text, message_obj)
        elif message_text == '/modes':
            return self._handle_list_modes_command(message_obj)
        elif message_text == '/current_mode':
            return self._handle_current_mode_command(message_obj)
        elif message_text in ['/ping', '/пинг']:
            self.send_sticker(
                message_obj['chat']['id'],
                'CAACAgIAAxkBAV1uWGeYms2Pm_xigAgwDcAfOTERmhbmAAL2AANWnb0K99tOIUA-pYo2BA',
                message_thread_id=message_obj.get('message_thread_id')
            )
            return True
        
        return False
    
    def _handle_set_mode_command(self, message_text: str, message_obj: dict) -> bool:
        """
        Handles the /set_mode command.
        
        Args:
            message_text: Text content of the message
            message_obj: Message object from Telegram
            
        Returns:
            True if command was processed
        """
        parts = message_text.split()
        chat_id = message_obj['chat']['id']
        message_thread_id = message_obj.get('message_thread_id', self.TG_BASE_THREAD_ID)
        
        if len(parts) != 2:
            # Invalid command format
            self.send_msg(
                chat_id=chat_id,
                text="Please specify the mode ID: /set_mode 1",
                message_thread_id=message_thread_id
            )
            return True
        
        mode_id = parts[1]
        
        if not self.agent or not hasattr(self.agent, 'mode_manager'):
            # Agent not initialized or doesn't have mode manager
            self.send_msg(
                chat_id=chat_id,
                text="Error: mode manager not initialized",
                message_thread_id=message_thread_id
            )
            return True
        
        # Switch mode
        result = self.agent.mode_manager.switch_mode(mode_id)
        
        self.send_msg(
            chat_id=chat_id,
            text=result,
            message_thread_id=message_thread_id
        )
        return True
    
    def _handle_list_modes_command(self, message_obj: dict) -> bool:
        """
        Handles the /modes command.
        
        Args:
            message_obj: Message object from Telegram
            
        Returns:
            True if command was processed
        """
        chat_id = message_obj['chat']['id']
        message_thread_id = message_obj.get('message_thread_id', self.TG_BASE_THREAD_ID)
        
        if not self.agent or not hasattr(self.agent, 'mode_manager'):
            # Agent not initialized or doesn't have mode manager
            self.send_msg(
                chat_id=chat_id,
                text="Error: mode manager not initialized",
                message_thread_id=message_thread_id
            )
            return True
        
        # Get list of modes
        modes = self.agent.mode_manager.list_available_modes()
        
        if not modes:
            self.send_msg(
                chat_id=chat_id,
                text="No available modes found",
                message_thread_id=message_thread_id
            )
            return True
        
        # Format message with modes list
        message = "Available modes:\n\n"
        for mode in modes:
            message += f"ID: {mode['id']} - <b>{mode['name']}</b>\n{mode['description']}\n\n"
        
        message += "To switch mode, use the command /set_mode ID"
        
        self.send_msg(
            chat_id=chat_id,
            text=message,
            message_thread_id=message_thread_id,
            parse_mode='HTML'
        )
        return True
    
    def _handle_current_mode_command(self, message_obj: dict) -> bool:
        """
        Handles the /current_mode command.
        
        Args:
            message_obj: Message object from Telegram
            
        Returns:
            True if command was processed
        """
        chat_id = message_obj['chat']['id']
        message_thread_id = message_obj.get('message_thread_id', self.TG_BASE_THREAD_ID)
        
        if not self.agent or not hasattr(self.agent, 'mode_manager'):
            # Agent not initialized or doesn't have mode manager
            self.send_msg(
                chat_id=chat_id,
                text="Error: mode manager not initialized",
                message_thread_id=message_thread_id
            )
            return True
        
        # Get current mode info
        mode_info = self.agent.mode_manager.get_current_mode_info()
        
        if "error" in mode_info:
            self.send_msg(
                chat_id=chat_id,
                text=f"Error: {mode_info['error']}",
                message_thread_id=message_thread_id
            )
            return True
        
        # Format message with mode info
        message = f"Current mode: <b>{mode_info['name']}</b> (ID: {mode_info['id']})\n"
        message += f"Description: {mode_info['description']}\n\n"
        
        message += "Active aspects:\n"
        for aspect in mode_info['active_aspects']:
            message += f"• <b>{aspect['name']}</b>: {aspect['description']}\n"
        
        self.send_msg(
            chat_id=chat_id,
            text=message,
            message_thread_id=message_thread_id,
            parse_mode='HTML'
        )
        return True
