"""
Staff communication module for handling Telegram communication with staff members.
Handles chat management, message sending, and thread operations.
"""
import logging
from typing import Optional, Dict, Any

class StaffCommunication:
    """
    Handles communication with staff members through Telegram.
    """
    
    def __init__(self, tg_tool, data_manager):
        """
        Initialize the staff communication handler.
        
        Args:
            tg_tool: Instance of TGTool for sending Telegram messages
            data_manager: Instance of StaffDataManager for accessing staff data
        """
        self.tg_tool = tg_tool
        self.data_manager = data_manager
        self.current_chat_id = None
        
        logging.info("StaffCommunication initialized")
    
    def open_telegram_chat(self, staff_telegram: str) -> str:
        """
        Open a chat with a staff member by their Telegram ID.
        
        Args:
            staff_telegram: Telegram ID of the staff member (e.g., "@username")
            
        Returns:
            Message with the result of the operation
        """
        try:
            logging.info(f"Attempting to open chat with staff member: {staff_telegram}")
            
            # Check if the staff member exists
            staff_list = self.data_manager.get_staff_list()
            
            # Debug output
            logging.info(f"Retrieved staff list: {len(staff_list)} entries")
            
            # Filter staff list, excluding items without "telegram_username"
            valid_staff_list = [s for s in staff_list if "telegram_username" in s]
            logging.info(f"Filtered staff list: {len(valid_staff_list)} entries")
            
            staff = next((s for s in valid_staff_list if s["telegram_username"] == staff_telegram), None)
            
            if not staff:
                return f"Staff member with Telegram ID {staff_telegram} not found"
            
            # Save current chat ID
            self.current_chat_id = staff_telegram
            
            # Remove notification for new message from this staff member
            self.data_manager.remove_notification(staff_telegram)
            
            # Ensure thread exists for this staff member
            self.ensure_employee_thread_exists(staff_telegram)
            
            return f"Opened chat with staff member: {staff['full_name']} ({staff_telegram})"
        except Exception as e:
            logging.error(f"Error opening chat: {e}")
            return f"An error occurred when opening chat: {str(e)}"
    
    def send_telegram_message_to(self, to_staff_telegram: str, msg: str) -> str:
        """
        Send a message to a staff member via Telegram.
        
        Args:
            to_staff_telegram: Telegram ID of the staff member
            msg: Text of the message
            
        Returns:
            Message with the result of the operation
        """
        try:
            # Check if the staff member exists
            staff_list = self.data_manager.get_staff_list()
            
            # Filter staff list, excluding items without "telegram_username"
            valid_staff_list = [s for s in staff_list if "telegram_username" in s]
            
            staff = next((s for s in valid_staff_list if s["telegram_username"] == to_staff_telegram), None)
            
            if not staff:
                return f"Staff member with Telegram ID {to_staff_telegram} not found"
            
            if "telegram_id" not in staff:
                return f"Staff member {to_staff_telegram} has no telegram_id specified"
            
            # Send message to the staff member's personal chat
            resp = self.tg_tool.send_msg(
                chat_id=staff['telegram_id'],
                text=msg
            )
            
            # Also forward the message to the staff member's thread in the supergroup
            thread_id = self.ensure_employee_thread_exists(to_staff_telegram)
            if thread_id:
                # Format message to indicate it's from the bot
                try:
                    formatted_message = f"Reply to staff member ({to_staff_telegram}):\n\n{msg}"
                    
                    self.tg_tool.send_msg(
                        chat_id=self.tg_tool.TG_CHAT_ID,
                        text=formatted_message,
                        message_thread_id=thread_id,
                        parse_mode="HTML"
                    )
                except Exception as thread_error:
                    logging.warning(f"Error sending to thread {thread_id}: {thread_error}")
            
            logging.info(f"Message to {to_staff_telegram}: {msg} {resp}")
            
            return f"Message sent to staff member {staff['full_name']} ({to_staff_telegram})\nresponse: {resp}"
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            return f"An error occurred when sending message: {str(e)}"
    
    def ensure_employee_thread_exists(self, staff_telegram: str) -> Optional[int]:
        """
        Ensure a thread exists for the staff member and create one if needed.
        
        Args:
            staff_telegram: Telegram ID of the staff member
            
        Returns:
            Thread ID, base thread ID, or None on error
        """
        # First log the attempt for better debugging
        logging.info(f"Checking if thread exists for {staff_telegram}")
        
        try:
            # Look for thread in file storage
            thread_id = self.data_manager.get_employee_thread_id(staff_telegram)
            
            if thread_id:
                logging.info(f"Found thread ID {thread_id} for {staff_telegram}")
                return thread_id
            
            # If thread not found or not accessible, create a new one
            logging.info(f"Creating new thread for {staff_telegram}")
            new_thread_id = self.create_employee_thread(staff_telegram)
            if new_thread_id:
                logging.info(f"Created new thread {new_thread_id} for {staff_telegram}")
                return new_thread_id
            
            # If unable to create thread, use base thread
            logging.warning(f"Unable to find or create thread for {staff_telegram}, using base thread")
            return self.tg_tool.TG_BASE_THREAD_ID
            
        except Exception as e:
            logging.error(f"Error checking if thread exists for {staff_telegram}: {e}")
            return self.tg_tool.TG_BASE_THREAD_ID  # Use base thread on error
    
    def create_employee_thread(self, staff_telegram: str) -> Optional[int]:
        """
        Create a new thread in the supergroup for a staff member.
        Also save the thread ID mapping for future lookup.
        
        Args:
            staff_telegram: Telegram ID of the staff member (e.g., "@username")
            
        Returns:
            ID of the created thread or None on error
        """
        try:
            # Get staff information
            staff_list = self.data_manager.get_staff_list()
            staff = next((s for s in staff_list if s.get("telegram_username") == staff_telegram), None)
            
            if not staff:
                logging.warning(f"Cannot create thread: staff member {staff_telegram} not found")
                return None
            
            # Create thread title
            thread_title = f"{staff.get('full_name', 'Unknown')} | {staff_telegram}"
            
            # Create thread in supergroup
            result = self.tg_tool.create_forum_topic(
                chat_id=self.tg_tool.TG_CHAT_ID,
                name=thread_title
            )
            
            if not result or 'message_thread_id' not in result:
                logging.error(f"Failed to create thread for {staff_telegram}: {result}")
                return None
            
            thread_id = result['message_thread_id']
            
            # Save thread ID in file storage
            self.data_manager.save_employee_thread_id(staff_telegram, thread_id)
            
            # Send welcome message to thread
            welcome_message = f"Thread for staff member {staff.get('full_name')} ({staff_telegram}) created.\n\n"
            welcome_message += "All messages from this staff member and bot replies will be displayed here."
            
            self.tg_tool.send_msg(
                chat_id=self.tg_tool.TG_CHAT_ID,
                text=welcome_message,
                message_thread_id=thread_id,
                parse_mode="HTML"
            )
            
            logging.info(f"Created thread {thread_id} for staff member {staff_telegram}")
            return thread_id
        except Exception as e:
            logging.error(f"Error creating thread for {staff_telegram}: {e}")
            return None
    
    def forward_message_to_thread(self, staff_telegram: str, message_text: str, 
                                  media_type: str = None, file_id: str = None) -> bool:
        """
        Forward a message from a staff member to their thread in the supergroup.
        Supports both text and media messages.
        
        Args:
            staff_telegram: Telegram ID of the staff member
            message_text: Text of the message or media description
            media_type: Type of media (voice, photo, document, etc.) or None for text
            file_id: File ID in Telegram for media messages
            
        Returns:
            True on success, False on error
        """
        try:
            # Get staff information for message prefix
            staff_list = self.data_manager.get_staff_list()
            staff = next((s for s in staff_list if s.get("telegram_username") == staff_telegram), None)
            staff_name = staff.get('full_name', 'Unknown') if staff else 'Unknown'
            
            # Try to get existing thread
            thread_id = self.ensure_employee_thread_exists(staff_telegram)
            if not thread_id:
                logging.warning(f"Unable to create thread for {staff_telegram}, using base thread")
                thread_id = self.tg_tool.TG_BASE_THREAD_ID
            
            # Format for indication that it's from the staff member
            formatted_message = message_text  # f"From {staff_name} ({staff_telegram}):\n\n{message_text}"
            
            # Send message with text in any case
            self.tg_tool.send_msg(
                chat_id=self.tg_tool.TG_CHAT_ID,
                text=formatted_message,
                message_thread_id=thread_id,
                parse_mode="HTML"
            )
            
            # If there's media content, send it as a separate message
            if media_type and file_id:
                try:
                    if media_type == "voice":
                        # Voice message
                        self.tg_tool.send_voice(
                            chat_id=self.tg_tool.TG_CHAT_ID,
                            voice=file_id,
                            message_thread_id=thread_id
                        )
                    elif media_type == "sticker":
                        # Sticker
                        self.tg_tool.send_sticker(
                            chat_id=self.tg_tool.TG_CHAT_ID,
                            sticker=file_id,
                            message_thread_id=thread_id
                        )
                    elif media_type == "video_note":
                        # Round video message
                        self.tg_tool.send_video_note(
                            chat_id=self.tg_tool.TG_CHAT_ID,
                            video_note=file_id,
                            message_thread_id=thread_id
                        )
                    else:
                        # For other types (photo, document, video, animation, etc.)
                        # use a general approach through Telegram API
                        params = {
                            'chat_id': self.tg_tool.TG_CHAT_ID,
                            'message_thread_id': thread_id,
                            'caption': f"Media from {staff_name} ({staff_telegram})"
                        }
                        
                        # Add parameter with media type (photo, document, etc.)
                        params[media_type] = file_id
                        
                        # Send through API method
                        method_name = f'send{media_type.capitalize()}'
                        self.tg_tool.method(method_name, params)
                except Exception as media_error:
                    logging.error(f"Error sending media content: {media_error}")
                    # Continue execution - text message has already been sent
            
            logging.info(f"Message from {staff_telegram} forwarded to thread {thread_id}")
            return True
        except Exception as e:
            logging.error(f"Error forwarding message from {staff_telegram}: {e}")
            return False
