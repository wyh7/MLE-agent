import os
from rich.live import Live
from rich.console import Console
from rich.markdown import Markdown

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from agent.utils import CONFIG_HOME
from agent.const import CONFIG_CHAT_HISTORY_FILE

HISTORY_PATH = str(os.path.join(CONFIG_HOME, CONFIG_CHAT_HISTORY_FILE))


class Chat:
    def __init__(self, llm_agent):
        """
        Initialize the chat class.
        :param llm_agent: the language model agent.
        """
        self.agent = llm_agent
        self.chat_history = []
        self.console = Console()
        self.session = PromptSession(history=FileHistory(HISTORY_PATH))

    def chat_generator(self, message: str):
        """
        Generate the chat.
        :param message: the user message.
        :return:
        """
        self.chat_history.append({"role": "user", "content": message})

        try:
            response = self.agent.completions(self.chat_history)
            for chunk in response:
                if chunk:
                    yield chunk
        except Exception as e:
            print(f"GeneratorError: {e}")

    def handle_streaming(self, prompt):
        """
        Handle the streaming of the chat.
        :param prompt: the user prompt.
        :return:
        """
        self.console.print(Markdown("**>**"), end=" ")
        text = ""
        block = "█ "
        with Live(console=self.console) as live:
            for token in self.chat_generator(prompt):
                content = token.choices[0].delta.content
                if content:
                    text = text + content
                if token.choices[0].finish_reason is not None:
                    block = ""
                markdown = Markdown(text + block)
                live.update(
                    markdown,
                    refresh=True,
                )
        self.chat_history.append({"role": "assistant", "content": text})

    def start(self):
        """
        Start the chat.
        :return: None
        """
        while True:
            try:
                self.handle_streaming(self.session.prompt("(Type to ask): ").strip())
            except (KeyboardInterrupt, EOFError):
                exit()