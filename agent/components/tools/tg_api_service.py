import time
import redis
import json
import os
import requests
import logging
import traceback
from redis import exceptions as redis_exceptions

logger = logging.getLogger('BaseLogger')


class TGAPI:
    __slots__ = ['token', 'session', 'API_URL', 'offset', 'timeout', 'redis_client']

    def __init__(self, token):
        self.session = requests.Session()
        self.token = token
        self.API_URL = 'https://api.telegram.org/bot{}/'.format(token)
        self.offset = 0
        self.timeout = 30
        
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=6379,
            decode_responses=True,
            password=os.getenv('REDIS_PASSWORD', None)
        )
        self.setWebhook(os.getenv('TG_WEBHOOK_URL'))

    def method(self, name, params, files=None):
        response = self.session.post(self.API_URL + name, data=params, files=files, timeout=self.timeout+5)
        if response.status_code != 200 and response.status_code != 400:
            raise Exception('error code: {}\ndesc: {}'.format(response.status_code, response.text))
    
        response = response.json()
        if not response['ok']:
            return response
        return response['result']
    
    def setWebhook(self, url):
        self.method('setWebhook', {'url': url})
    
    def process_updates(self):
        pubsub = self.redis_client.pubsub()
        try:
            pubsub.subscribe("bot_updates_channel")

            while True:
                try:
                    message = pubsub.get_message(timeout=1, ignore_subscribe_messages=True)

                    if message:
                        data = json.loads(message["data"])
                        yield data
                    else:
                        time.sleep(0.01)  # реализация херня, но так предложила нейронка, пока что лениво курить доку
                except redis_exceptions.ConnectionError:  # надо норм обработать
                    pass
                except json.JSONDecodeError as json_ex:
                    logger.error(f"JSON decoding error: {json_ex}")
                except Exception as ex:
                    traceback.print_exc()
                    logger.error(f"Error processing updates: {ex}")
                    time.sleep(1)
        except redis_exceptions.ConnectionError:
            print('ВКЛЮЧИ ВПН НЕ РАБОТАЕТ!!!!Ë')
            time.sleep(2)

    def getUpdates(self):
        response = self.method('getUpdates', {'offset': self.offset, 'timeout': self.timeout})

        for _event in response:
            self.offset = _event['update_id']
        if response:
            self.offset += 1
        return response

    def listen(self):
        while True:
            try:
                events = self.getUpdates()
                if not events:
                    continue

                for _event in events:
                    yield _event
            except KeyboardInterrupt:
                break
            except requests.exceptions.RequestException:
                time.sleep(1)
                continue
            except Exception as ex:
                logger.exception(f'ERROR LP TG: {ex}')
                continue

    def send_msg(self, chat_id, text, answer_to_message_id=None, message_thread_id=None, reply_markup=None, parse_mode=None):
        params = {'chat_id': chat_id,
                  'text': text,
                  'allow_sending_without_reply': True}
        if parse_mode:
            params['parse_mode'] = parse_mode
        if answer_to_message_id:
            params['reply_to_message_id'] = answer_to_message_id
        if message_thread_id and message_thread_id not in [1, "1"]:
            params['message_thread_id'] = message_thread_id
        if reply_markup:
            params['reply_markup'] = reply_markup
        
        logger.info(f"Sending message to {chat_id}: {text}\n{params}")
        return self.method('sendMessage', params)

    def edit_msg(self, chat_id, message_id, text, reply_markup=None, parse_mode=None):
        params = {'chat_id': chat_id,
                  'message_id': message_id,
                  'text': text}
        if reply_markup:
            params['reply_markup'] = reply_markup
        if parse_mode:
            params['parse_mode'] = parse_mode
        return self.method('editMessageText', params)
    
    def send_typing(self, chat_id, message_thread_id=None):
        params = {
            'chat_id': chat_id,
            'action': 'typing'
        }
        if message_thread_id:
            params['message_thread_id'] = message_thread_id
        return self.method('sendChatAction', params)
    
    def send_sticker(self, chat_id, sticker, answer_to_message_id=None, message_thread_id=None, reply_markup=None):
        params = {
            'chat_id': chat_id,
            'sticker': sticker
        }
        if answer_to_message_id:
            params['reply_to_message_id'] = answer_to_message_id
        if message_thread_id:
            params['message_thread_id'] = message_thread_id
        if reply_markup:
            params['reply_markup'] = reply_markup
        return self.method('sendSticker', params)
    
    def send_file(self, chat_id, document, caption=None, reply_markup=None, parse_mode=None, message_thread_id=None):
        """
        Use this method to send .webp stickers. On success, the sent Message is returned.
        :param chat_id: Unique identifier for the target chat or username of the target channel (in the format @channelusername)
        :param document: File to send. Pass a file_id as String to send a file that exists on the Telegram servers (recommended), pass an HTTP URL as a String for Telegram to get a file from the Internet, or upload a new one using multipart/form-data. More info on Sending Files »
        :param caption: Document caption (may also be used when resending documents by file_id), 0-200 characters
        :param reply_markup: Additional interface options. A JSON-serialized object for an inline keyboard, custom reply keyboard, instructions to remove reply keyboard or to force a reply from the user.
        :param parse_mode: Mode for parsing entities in the document caption. See formatting options for more details.
        :return: On success, the sent Message is returned.
        """
        params = {
            'chat_id': chat_id,
        }
        if caption:
            params['caption'] = caption
        if reply_markup:
            params['reply_markup'] = reply_markup
        if parse_mode:
            params['parse_mode'] = parse_mode
        if message_thread_id:
            params['message_thread_id'] = message_thread_id
    
        # Use the 'files' parameter to upload the file
        files = {'document': document}
        return self.method('sendDocument', params, files=files)
    
    def send_voice(self, chat_id, voice, caption=None, reply_markup=None, parse_mode=None, message_thread_id=None):
        """
        Use this method to send voice messages. On success, the sent Message is returned.
        Voice parameter can be either:
        - A file opened in binary mode
        - A file_id string (for forwarding existing voice messages)
        
        :param chat_id: Unique identifier for the target chat
        :param voice: Voice file or file_id string
        :param caption: Voice message caption (optional)
        :param reply_markup: Additional interface options (optional)
        :param parse_mode: Parse mode for caption (optional)
        :param message_thread_id: Thread ID for forum messages (optional)
        :return: Response from Telegram API
        """
        params = {
            'chat_id': chat_id,
        }
        if caption:
            params['caption'] = caption
        if reply_markup:
            params['reply_markup'] = reply_markup
        if parse_mode:
            params['parse_mode'] = parse_mode
        if message_thread_id:
            params['message_thread_id'] = message_thread_id
        
        # Check if voice is a string (file_id) or a file object
        if isinstance(voice, str):
            # If it's a string, it's a file_id - include directly in params
            params['voice'] = voice
            return self.method('sendVoice', params)
        else:
            # If it's a file object, use the files parameter
            files = {'voice': voice}
            return self.method('sendVoice', params, files=files)
    
    def send_video_note(self, chat_id, video_note, duration=None, length=None, thumb=None, reply_markup=None, message_thread_id=None):
        """
        Use this method to send video notes (round videos). On success, the sent Message is returned.
        :param chat_id: Unique identifier for the target chat or username of the target channel
        :param video_note: Video note to send. Pass a file_id as String to send a video note that exists on the Telegram servers (recommended) or upload a new video using multipart/form-data
        :param duration: Duration of sent video in seconds
        :param length: Video width and height, i.e. diameter of the video message
        :param thumb: Thumbnail of the file sent; can be ignored if thumbnail generation for the file is supported server-side
        :param reply_markup: Additional interface options. A JSON-serialized object for an inline keyboard, custom reply keyboard, instructions to remove reply keyboard or to force a reply from the user
        :param message_thread_id: Unique identifier for the target message thread (topic) of the forum; for forum supergroups only
        :return: On success, the sent Message is returned
        """
        params = {
            'chat_id': chat_id,
        }
        if duration:
            params['duration'] = duration
        if length:
            params['length'] = length
        if reply_markup:
            params['reply_markup'] = reply_markup
        if message_thread_id:
            params['message_thread_id'] = message_thread_id

        files = {'video_note': video_note}
        if thumb:
            files['thumb'] = thumb
        
        return self.method('sendVideoNote', params, files=files)
    
    def download_voice_file(self, file_id):
        file_path = self.method('getFile', {'file_id': file_id})["file_path"]
        
        download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        file_content = requests.get(download_url).content
        
        local_file_name = f"voice_message_{file_id[-10:]}.ogg"
        with open(local_file_name, "wb") as file:
            file.write(file_content)
        
        return local_file_name
