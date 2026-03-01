"""A chatbot that can use MCP servers.

Created by @pytholic on 2026.02.27
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
from typing import TypedDict, Any
from contextlib import AsyncExitStack

nest_asyncio.apply()

load_dotenv()
client = OpenAI()


class ToolDefinition(TypedDict):
    """A definition of a tool."""

    name: str
    description: str
    input_schema: dict[str, Any]


class MCPChatbot:
    """A chatbot that can use multiple MCP servers."""

    def __init__(self):
        self.mcp_clients: list[Client] = []
        self.openai_client = OpenAI()
        self.available_tools: list[FunctionToolParam] = []
        self.tool_to_mcp_client: dict[str, Client] = {}
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_name: str, server_config: dict[str, Any]):
        try:
            transport = StdioTransport(
                command=server_config["command"],
                args=server_config["args"],
                env=None,
                cwd=str(Path(__file__).parent),
            )
            mcp_client = Client(transport)

            await self.exit_stack.enter_async_context(mcp_client)
            self.mcp_clients.append(mcp_client)

            # List available tools
            tools = await mcp_client.list_tools()
            print(f"Connected to {server_name} with tools: {tools}")

            # Convert MCP tool schemas to OpenAI function tool format
            for tool in tools:
                self.tool_to_mcp_client[tool.name] = mcp_client
                self.available_tools.append(
                    {
                        "type": "function",
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    }
                )

        except Exception as e:
            print(f"Error connecting to {server_name}: {e}")
            raise e

    async def connect_to_servers(self):
        """Connect to all servers."""
        with open("server_config.json", "r") as f:
            data = json.load(f)

        servers = data.get("mcpServers", {})

        for server_name, server_config in servers.items():
            await self.connect_to_server(server_name, server_config)

    async def process_query(self, query: str) -> str:
        """Process a query and return the result."""

        messages: ResponseInputParam = [
            {
                "role": "system",
                "content": "You are a helpful assistant that can use the tools provided to answer questions.",
            },
            {"role": "user", "content": query},
        ]
        while True:
            response = self.openai_client.responses.create(
                model="gpt-5-nano",
                input=messages,
                tools=self.available_tools,
                tool_choice="auto",
                max_output_tokens=8192,
            )

            if response.status == "completed" and not any(
                item.type == "function_call" for item in response.output
            ):
                return response.output_text

            # Keep reasoning items only when followed by their required item
            output = response.output
            if output and output[-1].type == "reasoning":
                output = output[:-1]
            messages.extend(output)

            for item in response.output:
                if item.type == "function_call":
                    name = item.name
                    # Tool arguments are passed as a JSON string
                    # Can get truncated if max_output_tokens is not enough
                    arguments = json.loads(item.arguments)

                    print(f"Calling tool: {name} with arguments: {arguments}")

                    mcp_client = self.tool_to_mcp_client[name]
                    tool_result = await mcp_client.call_tool(name, arguments)

                    result = "\n".join(c.text for c in tool_result.content if hasattr(c, "text"))

                    messages.append(
                        {
                            "type": "function_call_output",
                            "call_id": item.call_id,
                            "output": result,
                        }
                    )

    async def chat_loop(self):
        """Interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")

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

    async def cleanup(self):
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()


async def main():
    chatbot = MCPChatbot()
    try:
        # the mcp clients and sessions are not initialized using "with"
        # like in the previous lesson
        # so the cleanup should be manually handled
        await chatbot.connect_to_servers()
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
