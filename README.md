# MCP Walkthrough

A step-by-step walkthrough of the Model Context Protocol (MCP) using [FastMCP](https://gofastmcp.com/) and OpenAI.

## Setup

```bash
# Install dependencies
uv sync

# Create .env with your OpenAI API key
echo "OPENAI_API_KEY=sk-..." > .env
```

## Project Structure

```
.
├── mcp_research_server.py          # MCP server with tools, resources, and prompts
├── mcp_chatbot.py                  # Multi-server MCP chatbot (tools only)
├── mcp_chatbot_resource_prompt_tool.py  # Full chatbot with tools + resources + prompts
├── server_config.json              # MCP server configuration
├── papers/                         # Stored paper data (created at runtime)
├── examples/                       # Step-by-step build-up files
│   ├── chatbot_tool_usage.py       # 1. OpenAI tool calling without MCP
│   └── mcp_chatbot.py             # 2. Single MCP server chatbot
└── pyproject.toml
```

## Progression

The files show a step-by-step build-up (earlier steps are in `examples/`):

1. `**examples/chatbot_tool_usage.py**` — Tool calling with OpenAI (no MCP). Defines tools as Python functions, manually creates JSON schemas, and wires up the tool execution loop.
2. `**examples/mcp_chatbot.py**` — Single MCP server chatbot. Replaces manual tool definitions with an MCP client that discovers tools from the server automatically.
3. `**mcp_chatbot.py**` — Multi-server chatbot. Connects to multiple MCP servers via `server_config.json`, routes tool calls to the correct server.
4. `**mcp_chatbot_resource_prompt_tool.py**` — Full-featured chatbot. Adds support for MCP resources (`@folders`, `@<topic>`) and prompts (`/prompt <name> <args>`).

## MCP Server

`mcp_research_server.py` exposes:

**Tools:**

- `search_papers(topic, max_results)` — Search arXiv and store paper info
- `extract_info(paper_id)` — Get stored info for a specific paper

**Resources:**

- `papers://folders` — List available topic folders
- `papers://{topic}` — Get paper details for a topic

**Prompts:**

- `generate_search_prompt(topic, num_papers)` — Generate a structured research prompt

### MCP Inspector UI

To inspect the MCP server in sandbox environment, run:

```bash
npx @modelcontextprotocol/inspector uv run mcp_research_server.py
```

## Running the Chatbot

### Chatbot Tool Usage Example

```
❯ uv run chatbot_tool_usage.py

User: Hi
Hello! How can I assist you today?
User: WHat are available tools that you can use?
I have access to the following tools:

1. **Paper Search Tool**: This tool allows me to search for papers on arXiv based on a specific topic and retrieve their information.

2. **Paper Info Extraction Tool**: This tool enables me to search for detailed information about a specific paper using its ID.

If you have any specific needs regarding research papers or topics, feel free to ask!
User: Search for 2 papers on "LLM interpretability"
Calling tool: search_papers with arguments: {'topic': 'LLM interpretability'}
Results are saved in: papers/llm_interpretability/papers_info.json
Calling tool: extract_info with arguments: {'paper_id': '2602.00462v3'}
Calling tool: extract_info with arguments: {'paper_id': '2407.04307v1'}
Here are two papers related to "LLM interpretability":

1. **Title**: [LatentLens: Revealing Highly Interpretable Visual Tokens in LLMs](https://arxiv.org/pdf/2602.00462v3)
   **Authors**: Benno Krojer, Shravan Nayak, Oscar Mañas, Vaibhav Adlakha, Desmond Elliott, Siva Reddy, Marius Mosbach
   **Published**: January 31, 2026
   **Summary**: This paper introduces "LatentLens," a method for mapping latent representations to natural language descriptions, allowing for improved interpretability of visual tokens when integrated with large language models (LLMs). The approach evaluates visual token representations across various vision-language models (VLMs), revealing that existing methods underestimate their interpretability. The findings suggest a close alignment between vision and language representations.

2. **Title**: [Crafting Large Language Models for Enhanced Interpretability](https://arxiv.org/pdf/2407.04307v1)
   **Authors**: Chung-En Sun, Tuomas Oikarinen, Tsui-Wei Weng
   **Published**: July 5, 2024
   **Summary**: This paper presents the Concept Bottleneck Large Language Model (CB-LLM), which aims to achieve inherent interpretability in LLMs. It features a built-in interpretability system and an Automatic Concept Correction (ACC) strategy that allows the model to maintain high accuracy while providing clear and accurate explanations, therefore enhancing transparency in language models.

If you need further details or assistance, feel free to ask!
User: bye
Goodbye!
```

### Chatbot with MCP Client

```
❯ uv run create_mcp_client.py

[02/27/26 00:52:01] INFO     Starting MCP server 'Research Assistant 🔎' with transport 'stdio'                             transport.py:183

Connected to server with tools: ['search_papers', 'extract_info']
User: hi
Hello! How can I help today? I can help you find papers on a topic, summarize articles, answer questions, or brainstorm ideas. Do you have a topic in mind or a task you'd like to tackle?


User: can you search for papers around physics and find just two of them for me
Calling tool: search_papers with arguments: {'topic': 'physics', 'max_results': 2}
Calling tool: extract_info with arguments: {'paper_id': '1910.11775v2'}
Calling tool: extract_info with arguments: {'paper_id': 'hep-ex/9605011v1'}
Here are two physics-related papers I found (as requested, I kept it to two):

- 1910.11775v2
  - Title: Physics Briefing Book
  - Authors: European Strategy for Particle Physics Preparatory Group
  - Published: 2019-10-25
  - Summary: A concise briefing book for the European Strategy Update process, summarizing community inputs and discussions on proposed projects and their importance.
  - PDF: https://arxiv.org/pdf/1910.11775v2

- hep-ex/9605011v1
  - Title: Physics and Technology of the Next Linear Collider: A Report Submitted to Snowmass '96
  - Authors: NLC ZDR Design Group; NLC Physics Working Group; S. Kuhlman
  - Published: 1996-05-30
  - Summary: Overview of the design and physics program for a future e+e− linear collider (500 GeV – 1 TeV) and its feasibility.
  - PDF: https://arxiv.org/pdf/hep-ex/9605011v1

Would you like me to fetch more details (e.g., full abstracts, BibTeX entries) or open/download the PDFs?
```

### Chatbot with Multiple MCP Servers

Input: Fetch ai.facebook.com, find an interesting term to search papers around, then summarize the findings and write them to a file called results.md

```
❯ uv run mcp_chatbot.py
```

### Tools, Resources, and Prompts

```bash
uv run mcp_chatbot_resource_prompt_tool.py
```

**Commands:**

- `@folders` — List available topics
- `@<topic>` — View papers for a topic
- `/prompts` — List available prompts
- `/prompt <name> <arg1=value1>` — Execute a prompt

**Example — Listing resources:**

```
Query: @folders

Resource: papers://folders
Content:
# Available Topics

- llm_interpretability
- chemistry
- machine_learning
- multimodal_transformers
- self-supervised_learning
- physics

Use @physics to access papers in that topic.
```

**Example — Reading a dynamic resource:**

```
Query: @physics

Resource: papers://physics
Content:
# Papers on Physics

Total papers: 2

## Physics Briefing Book
- **Paper ID**: 1910.11775v2
- **Authors**: European Strategy for Particle Physics Preparatory Group
- **Published**: 2019-10-25
- **PDF URL**: [https://arxiv.org/pdf/1910.11775v2](https://arxiv.org/pdf/1910.11775v2)

### Summary
The European Particle Physics Strategy Update (EPPSU) process takes a bottom-up approach, whereby the community is first invited to submit proposals (also called inputs) for projects that it would like to see realised in the near-term, mid-term and longer-term future. National inputs as well as inputs from National Laboratories are also an important element of the process. All these inputs are then reviewed by the Physics Preparatory Group (PPG), whose role is to organize a Symposium around the ...

---

## Physics and Technology of the Next Linear Collider: A Report Submitted to Snowmass '96
- **Paper ID**: hep-ex/9605011v1
- **Authors**: NLC ZDR Design Group, NLC Physics Working Group, S. Kuhlman
- **Published**: 1996-05-30
- **PDF URL**: [https://arxiv.org/pdf/hep-ex/9605011v1](https://arxiv.org/pdf/hep-ex/9605011v1)

### Summary
We present the current expectations for the design and physics program of an e+e- linear collider of center of mass energy 500 GeV -- 1 TeV. We review the experiments that would be carried out at this facility and demonstrate its key role in exploring physics beyond the Standard Model over the full range of theoretical possibilities. We then show the feasibility of constructing this machine, by reviewing the current status of linear collider technology and by presenting a precis of our `zeroth-o...

---
```

**Example — Listing and executing prompts:**

```
Query: /prompts

Available prompts:
- generate_search_prompt: Generate a prompt for Chatbot to find and discuss academic papers on a specific topic.
  Arguments:
    - topic
    - num_papers
- fetch: Fetch a URL and extract its contents as markdown
  Arguments:
    - url
```

```
Query: /prompt generate_search_prompt topic=math num_papers=3

Executing prompt 'generate_search_prompt'...
Calling tool: search_papers with arguments: {'topic': 'math', 'max_results': 3}
Calling tool: extract_info with arguments: {'paper_id': '2103.03874v2'}
Calling tool: extract_info with arguments: {'paper_id': '2312.01048v1'}
Calling tool: extract_info with arguments: {'paper_id': '2310.09590v2'}
```

## Claude Desktop Integration

Open Claude Desktop application. Go to `Developers > Edit Config` and open `claude_desktop_config.json` in a text editor.

Add our research server to the config:

```json
"mcpServers": {
    "research": {
      "command": "uv",
      "args": [
        "--directory",
        "<PROJECT ROOT>",
        "run",
        "mcp_research_server.py"
      ]
    }
  }
```

> **Note:** I had to replace `uv` with `/Users/username/.local/bin/uv` since Claude could not find it in PATH and threw `Failed to spawn process: No such file or directory`.

Restart Claude Desktop and run the following prompt:

```
Use the fetch tool to visit deeplearning.ai and find an interesting topic/keyword about machine learning on that web page.

Then research two papers on arxiv about that topic and summarize them.

Finally, generate a web-based quiz application with a set of flashcards based on the key topics in the papers

NOTE: I want you to use available research_server to search papers and extract info
```

> **Note:** If you do not add above `NOTE`, Claude starts using its own tools.

## Remote Server Deployment

Till now we worked with servers running locally using `stdio` transport. Now, we will create a remote server using FastMCP `Streamable HTTP` transport, test it using MCP inspector and then learn how to deploy it on `render.com`.

We update the main block in our `mcp_research_server.py`:

```python
if __name__ == "__main__":
    # Default: STDIO transport
    # mcp.run(transport="stdio")

    # Or use HTTP transport
    mcp.run(transport="http", host="127.0.0.1", port=9000)
```

### Run and test on local machine
Make sure all the required deps are installed (`uv sync`).

Run in terminal:

```
npx @modelcontextprotocol/inspector
```

Add the server URL `http://127.0.0.1:9000/mcp` and connect to the server.