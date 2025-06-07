import requests
import time

class VideoMessageTool:
    def __init__(self, tg_tool):
        """
        Initialize the VideoMessageTool with a reference to TGTool instance.
        
        Args:
            tg_tool: Instance of TGTool for sending Telegram messages
        """
        self.tg_tool = tg_tool
    
    def send_telegram_video_message(self, text: str) -> str:
        """
        Generates a video message using the provided API and sends it to Telegram.
        
        Args:
            text: Text content to be represented in the video message
            
        Returns:
            String describing the result of the operation
        """
        api_url = "http://127.0.0.1:5013/generate"
        params = {
            'text': text
        }
        t_s = time.time()
        
        try:
            response = requests.post(api_url, json=params)
            if response.status_code == 200:
                video_file = response.content
                self.tg_tool.send_video_note(
                    chat_id=self.tg_tool.TG_CHAT_ID, 
                    video_note=video_file, 
                    message_thread_id=self.tg_tool.TG_BASE_THREAD_ID
                )
                return "Video message was successfully sent!"
            else:
                return f"Failed to generate video message. Error: {response.status_code}"
        except Exception as e:
            return f"Error sending video message: {str(e)}"
