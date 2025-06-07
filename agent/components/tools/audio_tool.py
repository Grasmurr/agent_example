import requests
import time

class AudioTool:
    def __init__(self, tg_tool):
        """
        Initialize the AudioTool with a reference to TGTool instance.
        
        Args:
            tg_tool: Instance of TGTool for sending Telegram messages
        """
        self.tg_tool = tg_tool
    
    def send_telegram_voice_message(self, text: str) -> str:
        """
        Generates a voice message using the provided API and sends it to Telegram.
        
        Args:
            text: Text content to convert to speech
            
        Returns:
            String describing the result of the operation
        """
        api_url = "https://api.berht.dev/method/GenerationTTS"
        params = {
            'text': text,
            'v': 1,
            'access_token': "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbiI6IjM5Njg4Njk0NV8xNjUyMjA2NDQxIn0.Re1TBkp4MSgp4tq-cqOt33_5HENpPDtY098O5p8pocg"
        }
        t_s = time.time()
        
        try:
            response = requests.get(api_url, params=params)
            if response.status_code == 200:
                audio_file = response.content
                self.tg_tool.send_voice(
                    chat_id=self.tg_tool.TG_CHAT_ID, 
                    voice=audio_file, 
                    caption=f"Generated in {int(time.time() - t_s)} sec", 
                    message_thread_id=self.tg_tool.TG_BASE_THREAD_ID
                )
                return "Audio message was successfully sent!"
            else:
                return f"Failed to generate audio message. Error: {response.status_code}"
        except Exception as e:
            return f"Error sending audio message: {str(e)}"
