"""This script demonstrates how to use tools in a chatbot.

Created by @pytholic on 2026.02.26
"""

import json
import os
from pathlib import Path

import arxiv
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.responses import ResponseInputParam

# --------------------------------
# Tool Function Definition
# --------------------------------

PAPER_DIR = Path("papers")
PAPER_DIR.mkdir(exist_ok=True)


def search_papers(topic: str, max_results: int = 5) -> list[str]:
    """
    Search for papers on arXiv based on a topic and store their information.

    Args:
        topic: The topic to search for
        max_results: Maximum number of results to retrieve (default: 5)

    Returns:
        List of paper IDs found in the search
    """
    client = arxiv.Client()

    # Search for the most relevant articles matching the queried topic
    search = arxiv.Search(
        query=topic, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance
    )

    papers = client.results(search)

    # Store paper information in a directory
    path = PAPER_DIR / topic.lower().replace(" ", "_")
    path.mkdir(exist_ok=True)

    file_path = os.path.join(path, "papers_info.json")

    # Try to load existing papers info
    try:
        with open(file_path, "r") as json_file:
            papers_info = json.load(json_file)
    except (FileNotFoundError, json.JSONDecodeError):
        papers_info = {}

    # Process each paper and add to papers_info
    # Process each paper and add to papers_info
    paper_ids = []
    for paper in papers:
        if paper.get_short_id() not in papers_info:
            paper_info = {
                "title": paper.title,
                "authors": [author.name for author in paper.authors],
                "summary": paper.summary,
                "pdf_url": paper.pdf_url,
                "published": str(paper.published.date()),
            }
            papers_info[paper.get_short_id()] = paper_info
        paper_ids.append(paper.get_short_id())

    # Save updated papers_info to json file
    with open(file_path, "w") as json_file:
        json.dump(papers_info, json_file, indent=2)

    print(f"Results are saved in: {file_path}")

    return paper_ids


def extract_info(paper_id: str) -> str:
    """
    Search for information about a specific paper across all topic directories.

    Args:
        paper_id: The ID of the paper to look for

    Returns:
        JSON string with paper information if found, error message if not found
    """

    for item in PAPER_DIR.iterdir():
        if item.is_dir():
            file_path = item / "papers_info.json"
            if file_path.is_file():
                try:
                    with open(file_path, "r") as json_file:
                        papers_info = json.load(json_file)
                        if paper_id in papers_info:
                            return json.dumps(papers_info[paper_id], indent=2)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print(f"Error reading {file_path}: {str(e)}")
                    continue

    return f"There's no saved information related to paper {paper_id}."


# --------------------------------
# Tool Schema Definition
# --------------------------------

# Reference: https://developers.openai.com/api/docs/guides/function-calling#function-tool-example
tools = [
    {
        "type": "function",
        "name": "search_papers",
        "description": "Search for papers on arXiv based on a topic and store their information.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The topic to search for"},
            },
            "required": ["topic"],
        },
    },
    {
        "type": "function",
        "name": "extract_info",
        "description": "Search for information about a specific paper across all topic directories.",
        "parameters": {
            "type": "object",
            "properties": {
                "paper_id": {"type": "string", "description": "The ID of the paper to look for"}
            },
            "required": ["paper_id"],
        },
    },
]

# --------------------------------
# Tool Mapping
# --------------------------------

tool_mapping = {
    "search_papers": search_papers,
    "extract_info": extract_info,
}


def execute_tool(tool_name: str, tool_args: dict) -> str:
    """
    Execute a tool based on the tool name and its parameters.
    """
    result = tool_mapping[tool_name](**tool_args)

    if result is None:
        result = "The operation completed but didn't return any results."

    elif isinstance(result, list):
        result = ", ".join(result)

    elif isinstance(result, dict):
        # Convert dictionaries to formatted JSON strings
        result = json.dumps(result, indent=2)

    else:
        # For any other type, convert using str()
        result = str(result)
    return result


# --------------------------------
# Chatbot Code
# --------------------------------
load_dotenv()
client = OpenAI()


def process_query(query: str) -> str:
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

    # Ref: https://developers.openai.com/api/docs/guides/function-calling#handling-function-calls
    while True:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=messages,
            tools=tools,  # type: ignore[arg-type]
            tool_choice="auto",
        )

        # If no tool calls, we have the final answer
        if response.status == "completed" and not any(
            item.type == "function_call" for item in response.output
        ):
            return response.output_text

        # Process all tool calls
        messages.extend(response.output)

        for item in response.output:
            if item.type == "function_call":
                name = item.name
                arguments = json.loads(item.arguments)

                print(f"Calling tool: {name} with arguments: {arguments}")

                # When the model calls a function, you must execute it and return the result.
                result = execute_tool(name, arguments)
                messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": result,
                    }
                )


def chatbot_loop():
    while True:
        try:
            query = input("User: ")
            if query.lower() in ["exit", "quit", "bye"]:
                print("Goodbye!")
                break
            print(process_query(query))
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    chatbot_loop()
