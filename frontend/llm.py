import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("Websockets package not found. Make sure it's installed.")

from collections import deque

class PromptState:
    def __init__(self, base_prompt, stopping_string, reverse, keep = 5):
        self.base_prompt = base_prompt.strip()
        self.stopping_string = stopping_string
        self.reverse = reverse
        self.prompts = deque([])
        self.keep = keep


    def build_prompt(self):
        full_prompt = self.base_prompt
        for p in self.prompts:
            full_prompt += '\n'
            full_prompt += p
        return full_prompt

    def add_question(self, question):
        line = f"{self.stopping_string} {question}"
        self.prompts.append(line)

        full_prompt = self.build_prompt()
        return full_prompt

    def extract_response(self, prompt):
        #response = prompt.removeprefix(self.build_prompt()).strip()
        response = prompt.strip();
        self.prompts.append(response)

        if len(self.prompts) > self.keep * 2:
            self.prompts.popleft()
            self.prompts.popleft()

        return response.removeprefix(self.reverse).strip()

# For local streaming, the websockets are hosted without ssl - ws://
HOST = 'dev.exopticon.org:5005'
URI = f'ws://{HOST}/api/v1/stream'

# For reverse-proxied streaming, the remote will likely host with ssl - wss://
# URI = 'wss://your-uri-here.trycloudflare.com/api/v1/stream'


async def run(context):
    # Note: the selected defaults change from time to time.
    request = {
        'prompt': context,
        'max_new_tokens': 250,
        'do_sample': True,
        'temperature': 1.3,
        'top_p': 0.1,
        'typical_p': 1,
        'repetition_penalty': 1.18,
        'top_k': 40,
        'min_length': 0,
        'no_repeat_ngram_size': 0,
        'num_beams': 1,
        'penalty_alpha': 0,
        'length_penalty': 1,
        'early_stopping': True,
        'seed': -1,
        'add_bos_token': True,
        'truncation_length': 2048,
        'ban_eos_token': False,
        'skip_special_tokens': True,
        'stopping_strings': ['\nUser: ']
    }

    async with websockets.connect(URI, ping_interval=None) as websocket:
        await websocket.send(json.dumps(request))

#        yield context  # Remove this if you just want to see the reply

        while True:
            incoming_data = await websocket.recv()
            incoming_data = json.loads(incoming_data)

            match incoming_data['event']:
                case 'text_stream':
                    yield incoming_data['text']
                case 'stream_end':
                    return

async def print_response_stream(prompt):
    full_response = ''
    async for response in run(prompt):
        full_response += response
        print(response, end='')
        sys.stdout.flush()  # If we don't flush, we won't see tokens in realtime.
    return full_response


prompt = '''Transcript of a dialog, where the User interacts with an Assistant named Bob. Bob is helpful, kind, honest, good at writing, and never fails to answer the User's requests immediately and with precision.

User: Hello, Bob.
Bob: Hello. How may I help you today?
User: Please tell me the largest city in Europe.
Bob: Sure. The largest city in Europe is Moscow, the capital of Russia.
'''


if __name__ == '__main__':
    #prompt = "In order to make homemade bread, follow these steps:\n1)"
#    prompt = "The following is a dialog between two crazy people:\nJohn: Hey how are you?\nAmy: "
    state = PromptState(prompt, 'User:', 'Bob:')
    new_prompt = state.add_question('Where do llamas come from?')
    full_response = asyncio.run(print_response_stream(new_prompt))
    r = state.extract_response(full_response)
    print(f"\n\nResponse: {r}\n\n")
