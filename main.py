from http import client
import json
from pyexpat.errors import messages
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
    }
]

@app.get("/")
async def health_check():
    return {"status": "OfficePilot is running"}


@app.post("/chat")
async def chat(request: ChatRequest):
    messages = [
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

        if tool_name == "get_recent_commits":
            result = await get_recent_commmits()
        else:
            return {"error": f"Unknown tool: {tool_name}"}

        messages.append({
            "role": "tool",
            "tool_name": tool_name,
            "content": json.dumps(result),
        })

    # Step 4: Ask Ollama to explain the tool's result.
    final_response = await ollama_client.chat(
        model="qwen3:4b",
        messages=messages,
    )

    return {"reply": final_response.message.content}

async def get_recent_commmits():
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
    return await get_recent_commmits()


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
                "url":item["html_url"]
            }
            for item in pull_requests
        ]

@app.get("/github/pull_requests")
async def github_pull_requests():
    return await get_recent_pull_request()