import json
from anthropic import Anthropic
from anthropic.types import Message
from dotenv import load_dotenv

# Load environment variables
'''
.env file must contain ANTHROPIC_API_KEY
'''
load_dotenv()
client = Anthropic()

class ClaudeResponses:
    '''
    Generates Claude responses.
    User can save history by calling add_user_message.
    Use chat("user_input") for a single response (no history is saved).
    Includes tool use.
    Parameters:
        model (str): model to use. Choose from:
            Claude Opus 4.1 | claude-opus-4-1-20250805
            Claude Opus 4 | claude-opus-4-20250514
            Claude Sonnet 4 | claude-sonnet-4-20250514
            Claude Sonnet 3.7 | claude-3-7-sonnet-20250219
            Claude Haiku 3.5 | claude-3-5-haiku-20241022
            Claude Haiku 3 | claude-3-haiku-20240307
        messages (list): list of messages to send to the model.
        system_prompt (str): system prompt to send to the model.
        model_params (dict): parameters to send to the model.
        save_history (bool): whether to save user and assistant messages to self.messages.
    '''
    def __init__(self, 
                 model: str = "Claude Haiku 3.5",
                 system_prompt: str | None= None,
                 model_params: dict | None = None,
                 tools: list | None = None,
                 save_history: bool = True) -> None:
        match model:
            case "Claude Opus 4.1" | "Opus 4.1" | "claude-opus-4-1-20250805":
                self.model = "claude-opus-4-1-20250805"
            case "Claude Opus 4" | "Opus 4" | "claude-opus-4-20250514":
                self.model = "claude-opus-4-20250514"
            case "Claude Sonnet 4" | "Sonnet 4" | "claude-sonnet-4-20250514":
                self.model = "claude-sonnet-4-20250514"
            case "Claude Sonnet 3.7" | "Sonnet 3.7" | "claude-3-7-sonnet-20250219":
                self.model = "claude-3-7-sonnet-20250219"
            case "Claude Haiku 3.5" | "Haiku 3.5" | "claude-3-5-haiku-20241022":
                self.model = "claude-3-5-haiku-20241022"
            case "Claude Haiku 3" | "Haiku 3" | "claude-3-haiku-20240307":
                self.model = "claude-3-haiku-20240307"
            case _:
                self.model = model
    
        self.system_prompt = system_prompt
        self.model_params = model_params
        self.tools = tools
        self.save_history = save_history
        self.messages = []
    
    def _reset_history(self):
        self.messages = []

    def add_user_message(self, message: str | Message | list):
        text = message.content if isinstance(message, Message) else message
        user_mesage = {
            "role": "user",
            "content": text
        }
        self.messages.append(user_mesage)

    def add_assistant_message(self, message: str | Message):
        text = message.content if isinstance(message, Message) else message
        assistant_mesage = {
            "role": "assistant",
            "content": text
        }
        self.messages.append(assistant_mesage)

    def _build_params(self,
                      model: str,
                      message_history: list[dict],
                      **kwargs
    ):
        """
        Build the params dict for Anthropic's Messages API.
        """
        # Base defaults
        params = {
            "model": model,
            "messages": message_history,
            "max_tokens": 1000,
        }

        # Merge user-specified defaults from init (without mutating self.model_params)
        if self.model_params:
            params.update(dict(self.model_params))
        
        # Include system prompt unless caller overrides it
        if self.system_prompt and "system" not in kwargs:
            params["system"] = self.system_prompt

        # Include system prompt unless caller overrides it
        if self.tools and "tools" not in kwargs:
            params["tools"] = self.tools
            
        # Per-call model_params (temperature, top_p, stop_sequences, system, etc.)
        if kwargs:
            params.update(kwargs)

        return params

    def _run_tools(self, message: Message):
        tool_requests = [
            block for block in message.content if block.type == "tool_use"
        ]
        tool_result_blocks = []
        for tool_request in tool_requests:
            try: 
                tool_output = eval(f"{tool_request.name}(**{tool_request.input})")
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": tool_request.id,
                    "content": json.dumps(tool_output),
                    "is_error": False
                }
            except Exception as e:
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": tool_request.id,
                    "content": f"Error: {e}",
                    "is_error": True
                }
            tool_result_blocks.append(tool_result_block)
        
        return tool_result_blocks

    def chat(self, 
             user_input: str | None = None,
             messages: list[dict] | None = None,
             model: str | None = None,
             return_text: bool = False,
             print_partial_response: bool = False
             **kwargs):
        '''
        Sends a message to the model and returns the response.
        Parameters:
            user_input (str): message to send to the model.
            messages (list): list of messages to send to the model; defaults to self.messages.
            model (str): model to use.
            return_text (bool): whether to return the text of the response as an object.
            **kwargs: additional parameters to send to the model.
        Returns:
            str: response from the model.
        '''
        # Retreive message history
        # Check for input
        if not user_input and not messages and not self.messages:
            raise ValueError("No user input provided (please set user_input or messages).")
        
        # Save messages 
        if self.save_history and user_input:
            self.add_user_message(user_input)
        
        # Retreive model
        model_to_use = model or self.model
        
        history = list(messages) if messages is not None else list(self.messages)
        
        if history:
            message_history = history 
            if user_input and not self.save_history:
                message_history = message_history + [{"role": "user", "content": user_input}]
        else:
            message_history = [{"role": "user", "content": user_input}]
            
        # Run conversation
        text_blocks = []
        while True:
            # Retreive model params
            params = self._build_params(model_to_use, message_history,**kwargs)
            # Send message to model
            resp = client.messages.create(**params)
            message_history.append({"role": "assistant", "content": resp.content})

            # Save to history
            if self.save_history:
                self.add_assistant_message(resp)
            
            text_blocks += [block.text for block in resp.content if block.type == "text"]
            partial_response = "\n".join([block.text for block in resp.content if block.type == "text"]) if [block.text for block in resp.content if block.type == "text"] else ""
            
            if print_partial_response:
                print(partial_response)

            if resp.stop_reason != "tool_use":
                break
            
            # Run tools
            tool_result_blocks = self._run_tools(resp)
            message_history.append({"role": "user", "content": tool_result_blocks})

            if self.save_history:
                self.add_user_message(tool_result_blocks)
            

        
        final_response = "\n".join(text_blocks) if text_blocks else ""

        if return_text:
            return final_response
        
