import json
from fastapi import FastAPI
from pydantic import BaseModel
from ollama import AsyncClient
import os
import httpx
from dotenv import load_dotenv
load_dotenv()
app= FastAPI(title="Office API")
ollama_client = AsyncClient(host="http://localhost:11434")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")

class ChatRequest(BaseModel):
    message:str

# Define the tools available for the chat model
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_commits",
            "description": (
                "Fetch the five most recent commits from the "
                "configured GitHub repository, including commit "
                "message, author, date, and URL."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
    "type": "function",
    "function": {
            "name": "get_recent_pull_request",
            "description": "Fetch the five most recent pull requests from the configured GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


@app.get("/")
async def health_check():
    return {"status": "OfficePilot is running"}


@app.post("/chat")
async def chat(request: ChatRequest):
    messages = [
    {
        "role": "system",
        "content": (
            "You are OfficePilot, an AI developer assistant. "
            "Use get_recent_commits when the user asks about "
            "GitHub commits. Use get_recent_pull_request when "
            "the user asks about pull requests. "
            "Never invent GitHub data."
        )
    },
    {"role": "user", "content": request.message}
    ]

    # Step 1: Ask Ollama whether it needs a tool.
    response = await ollama_client.chat(
        model="qwen3:4b",
        messages=messages,
        tools=tools,
    )

    tool_calls = response.message.tool_calls or []

    # Step 2: If no tool is requested, return the normal answer.
    if not tool_calls:
        return {"reply": response.message.content}

    # Step 3: Execute the requested tool.
    messages.append(response.message)

    for tool_call in tool_calls:
        tool_name = tool_call.function.name

        tool_function = tool_registry.get(tool_name)

    
        if tool_name == "get_recent_commits":
            result = await get_recent_commits()
        elif tool_name == "get_recent_pull_request":
            result = await get_recent_pull_request()
        else:
            return {"error": f"Unknown tool: {tool_name}"}

        messages.append({
            "role": "tool",
            "tool_name": tool_name,
            "content": json.dumps(result),
        })
        # if tool_function is None:
        # return {"error": f"Unknown tool: {tool_name}"}

    # Step 4: Ask Ollama to explain the tool's result.
    final_response = await ollama_client.chat(
        model="qwen3:4b",
        messages=messages,
    )

    return {"reply": final_response.message.content}

async def get_recent_commits():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits"
    headers = {
        "Accept":"application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    async with httpx.AsyncClient(timeout=15.0) as Client:
        response = await Client.get(
            url,headers=headers,params={"per_page": 5}
        )

        response.raise_for_status()
        commits = response.json()
    return [
        {
            "message": item["commit"]["message"],
            "author":  item["commit"]["author"]["name"],
            "date": item["commit"]["author"]["date"],
            "url": item["html_url"]
        }
        for item in commits
    ]

@app.get("/github/commits")
async def github_commits():
    return await get_recent_commits()


async def get_recent_pull_request():
    url = ( f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls")
    headers = {
        "Accept":"application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    params = {"state":"all","sort":"created","direction":"desc","per_page":5}
    async with httpx.AsyncClient(timeout=15.0) as Client:
        response = await Client.get(
            url,headers=headers,params=params
        )

        response.raise_for_status()
        pull_requests = response.json()
        return [
            {
                "title": item["title"],
                "author": item["user"]["login"],
                "state": item["state"],
                "created_at": item["created_at"],
                "url": item["html_url"],
                "draft": item["draft"],
                "description": item["body"]
            }
            for item in pull_requests
        ]

@app.get("/github/pull_requests")
async def github_pull_requests():
    return await get_recent_pull_request()

tool_registry = {
    "get_recent_commits": get_recent_commits,
    "get_recent_pull_request": get_recent_pull_request
}

async def get_pull_request_details(pr_number:int):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls/{pr_number}"
    headers = {
        "Accept":"application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url,headers = headers)
        response.raise_for_status()
        pr_details = response.json()
        return {
            "title": pr_details["title"],
            "author": pr_details["user"]["login"],
            "state": pr_details["state"],
            "created_at": pr_details["created_at"],
            "url": pr_details["html_url"],
            "draft": pr_details["draft"],
            "description": pr_details["body"],
        }

# this api gets the data for a specific pull request by its number
@app.get("/github/pull_requests/{pr_number}")
async def github_pull_request_details(pr_number:int):
    return await get_pull_request_details(pr_number)