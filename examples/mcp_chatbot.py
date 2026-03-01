"""A chatbot that can use our MCP research server.

Created by @pytholic on 2026.02.26
"""

import asyncio
import json
from pathlib import Path

import nest_asyncio
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from openai import OpenAI
from openai.types.responses import FunctionToolParam, ResponseInputParam

nest_asyncio.apply()

load_dotenv()
client = OpenAI()


# --------------------------------
# Build chatbot with MCP Client
# --------------------------------


class MCPChatbot:
    def __init__(self):
        # Initialize clients
        self.mcp_client: Client | None = None  # type: ignore[type-arg]
        self.openai_client = OpenAI()
        self.available_tools: list[FunctionToolParam] = []

    async def process_query(self, query: str) -> str:
        """
        Process a query and return the result.
        """
        messages: ResponseInputParam = [
            {
                "role": "system",
                "content": "You are a helpful assistant that can use the tools provided to answer questions.",
            },
            {"role": "user", "content": query},
        ]
        while True:
            # Ref: https://github.com/openai/openai-python/blob/656e3cab4a18262a49b961d41293367e45ee71b9/src/openai/resources/responses/responses.py#L113
            response = self.openai_client.responses.create(
                model="gpt-5-nano",
                input=messages,
                tools=self.available_tools,
                tool_choice="auto",
                max_output_tokens=2048,
            )

            if response.status == "completed" and not any(
                item.type == "function_call" for item in response.output
            ):
                return response.output_text

            messages.extend(response.output)

            for item in response.output:
                if item.type == "function_call":
                    name = item.name
                    arguments = json.loads(item.arguments)

                    print(f"Calling tool: {name} with arguments: {arguments}")

                    # Tool invocation through the MCP client session
                    tool_result = await self.mcp_client.call_tool(name, arguments)
                    result = json.dumps([c.model_dump() for c in tool_result.content])
                    messages.append(
                        {
                            "type": "function_call_output",
                            "call_id": item.call_id,
                            "output": result,
                        }
                    )

    async def chat_loop(self):
        """
        Chat loop.
        """
        while True:
            try:
                query = input("User: ")
                if query.lower() in ["exit", "quit", "bye"]:
                    print("Goodbye!")
                    break
                result = await self.process_query(query)
                print(result)
                print("\n")
            except Exception as e:
                print(f"Error: {e}")

    async def connect_to_server_and_run(self):
        """
        Connect to the MCP server and run the chat loop.
        """
        transport = StdioTransport(
            command="uv",
            args=["run", "create_mcp_server.py", "--verbose"],
            env=None,
            cwd=str(Path(__file__).parent),
        )

        self.mcp_client = Client(transport)

        async with self.mcp_client:
            # Basic server interaction
            await self.mcp_client.ping()

            # List available operations
            tools = await self.mcp_client.list_tools()
            print("\nConnected to server with tools:", [tool.name for tool in tools])

            # Convert MCP tool schemas to OpenAI function tool format
            self.available_tools = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                }
                for tool in tools
            ]

            # will call chat_loop here
            await self.chat_loop()


async def main():
    chatbot = MCPChatbot()
    await chatbot.connect_to_server_and_run()


if __name__ == "__main__":
    asyncio.run(main())
