"""A chatbot that can use MCP servers.

RESOURCES:
static URI: papers://folders (which represents the list of available topics)
dynamic URI: papers://{topic} (which represents the papers' information under the topic specified by the client during runtime)

Created by @pytholic on 2026.02.27
"""

import asyncio
import json
from pathlib import Path

import nest_asyncio
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
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
        # Client dict maps names/URI to MCP clients
        self.mcp_clients: dict[str, Client] = {}
        self.openai_client = OpenAI()
        # Tool list required by OpenAI API
        self.available_tools: list[FunctionToolParam] = []
        # Prompt list for quick display
        self.available_prompts: list[str] = []
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_name: str, server_config: dict[str, Any]):
        try:
            if "url" in server_config:
                transport = StreamableHttpTransport(url=server_config["url"])
                print(f"Connected to {server_name} with URL: {server_config['url']}")
            else:
                transport = StdioTransport(
                    command=server_config["command"],
                    args=server_config["args"],
                    env=None,
                    cwd=str(Path(__file__).parent),
                )
                print(
                    f"Connected to {server_name} with command: {server_config['command']} and args: {server_config['args']}"
                )
            mcp_client = Client(transport)

            await self.exit_stack.enter_async_context(mcp_client)

            # List available tools
            tools = await mcp_client.list_tools()
            tool_names = [t.name for t in tools]
            print(f"Connected to {server_name} with tools: {tool_names}")

            # Convert MCP tool schemas to OpenAI function tool format
            for tool in tools:
                self.mcp_clients[tool.name] = mcp_client
                self.available_tools.append(
                    {
                        "type": "function",
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    }
                )

            # List available resources (not all servers support this)
            try:
                resources = await mcp_client.list_resources()
            except Exception:
                resources = []
            if resources:
                resource_uris = [str(r.uri) for r in resources]
                print(f"Connected to {server_name} with resources: {resource_uris}")
                for resource in resources:
                    resource_uri = str(resource.uri)
                    self.mcp_clients[resource_uri] = mcp_client

            # List available prompts (not all servers support this)
            try:
                prompts = await mcp_client.list_prompts()
            except Exception:
                prompts = []
            if prompts:
                prompt_names = [p.name for p in prompts]
                print(f"Connected to {server_name} with prompts: {prompt_names}")
                for prompt in prompts:
                    prompt_name = str(prompt.name)
                    self.mcp_clients[prompt_name] = mcp_client

                    # Convert MCP prompt arguments to OpenAI function parameters
                    # Ref: https://github.com/PrefectHQ/fastmcp/blob/72129c3d0379e1f866fb2bb47e56f9d32388bb8b/src/fastmcp/prompts/prompt.py#L96
                    props = {}
                    required = []
                    for arg in prompt.arguments:
                        props[arg.name] = {
                            "type": "string",
                            "description": arg.description,
                        }
                        if arg.required:
                            required.append(arg.name)

                    self.available_prompts.append(
                        {
                            "type": "function",
                            "name": prompt.name,
                            "description": prompt.description,
                            "parameters": {
                                "type": "object",
                                "properties": props,
                                "required": required,
                            },
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

                    mcp_client = self.mcp_clients[name]
                    tool_result = await mcp_client.call_tool(name, arguments)

                    result = "\n".join(c.text for c in tool_result.content if hasattr(c, "text"))

                    messages.append(
                        {
                            "type": "function_call_output",
                            "call_id": item.call_id,
                            "output": result,
                        }
                    )

    async def get_resource(self, resource_uri):
        """Get a resource from the MCP server."""
        mcp_client = self.mcp_clients.get(resource_uri)

        # Fallback for dynamic URIs - find a client registered for the same scheme
        if not mcp_client:
            scheme = resource_uri.split("://")[0] + "://"
            for uri, client in self.mcp_clients.items():
                if uri.startswith(scheme):
                    mcp_client = client
                    break

        if not mcp_client:
            print(f"Resource '{resource_uri}' not found.")
            return

        try:
            contents = await mcp_client.read_resource(resource_uri)
            if contents and hasattr(contents[0], "text"):
                print(f"\nResource: {resource_uri}")
                print("Content:")
                print(contents[0].text)
            else:
                print("No content available.")
        except Exception as e:
            print(f"Error: {e}")

    async def list_prompts(self):
        """List all available prompts."""
        if not self.available_prompts:
            print("No prompts available.")
            return

        print("\nAvailable prompts:")
        for prompt in self.available_prompts:
            print(f"- {prompt['name']}: {prompt['description']}")
            properties = prompt["parameters"].get("properties", {})
            if properties:
                print("  Arguments:")
                for arg_name in properties:
                    print(f"    - {arg_name}")

    async def execute_prompt(self, prompt_name: str, arguments: dict[str, Any]):
        """Execute a prompt with the given arguments."""
        client = self.mcp_clients[prompt_name]
        if not client:
            print(f"Prompt '{prompt_name}' not found.")
            return

        try:
            result = await client.get_prompt(prompt_name, arguments)
            if result and result.messages:
                prompt_content = result.messages[0].content

                # Extract text from content (handles different formats)
                if isinstance(prompt_content, str):
                    text = prompt_content
                elif hasattr(prompt_content, "text"):
                    text = prompt_content.text
                else:
                    # Handle list of content items
                    text = " ".join(
                        item.text if hasattr(item, "text") else str(item) for item in prompt_content
                    )

                print(f"\nExecuting prompt '{prompt_name}'...")
                await self.process_query(text)
        except Exception as e:
            print(f"Error: {e}")
            raise e

    async def chat_loop(self):
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        print("Use @folders to see available topics")
        print("Use @<topic> to search papers in that topic")
        print("Use /prompts to list available prompts")
        print("Use /prompt <name> <arg1=value1> to execute a prompt")

        while True:
            try:
                query = input("\nQuery: ").strip()
                if not query:
                    continue

                if query.lower() in ["exit", "quit", "bye"]:
                    print("Goodbye!")
                    break

                # Check for @resource syntax first
                if query.startswith("@") and len(query) > 1:
                    # remove the @
                    topic = query[1:]
                    if topic == "folders":
                        resource_uri = "papers://folders"
                    else:
                        resource_uri = f"papers://{topic}"
                    await self.get_resource(resource_uri)
                    continue

                # Check for /command syntax
                if query.startswith("/") and len(query) > 1:
                    parts = query.split()
                    command = parts[0][1:]
                    if command == "prompts":
                        await self.list_prompts()
                    elif command == "prompt":
                        if len(parts) < 2:
                            print("Usage: /prompt <name> <arg1=value1>...")
                            continue

                        prompt_name = parts[1]
                        prompt_args = {}

                        # Parse arguments
                        for arg in parts[2:]:
                            if "=" in arg:
                                key, value = arg.split("=", 1)
                                prompt_args[key] = value

                        await self.execute_prompt(prompt_name, prompt_args)
                    else:
                        print(f"Unknown command: {command}")
                    continue

                await self.process_query(query)
                print("\n")

            except Exception as e:
                print(f"Error: {e} ({type(e).__name__})")

    async def cleanup(self):
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()


async def main():
    chatbot = MCPChatbot()
    try:
        await chatbot.connect_to_servers()
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
