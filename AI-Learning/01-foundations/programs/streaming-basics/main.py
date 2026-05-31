"""
Streaming Basics - FastAPI server comparing streaming vs non-streaming LLM responses.

Demonstrates:
1. Non-streaming endpoint (wait for full response)
2. SSE streaming endpoint (tokens arrive as generated)
3. Time-to-first-token comparison
4. Simple HTML client for testing
"""

import json
import time
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()

app = FastAPI(title="Streaming Basics Demo")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"


class ChatRequest(BaseModel):
    message: str
    max_tokens: int = 500


# --- Non-streaming endpoint ---

@app.post("/chat")
async def chat_non_streaming(request: ChatRequest):
    """Standard non-streaming response. Client waits for full completion."""
    start = time.time()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": request.message}],
        max_tokens=request.max_tokens,
    )

    elapsed = time.time() - start

    return {
        "response": response.choices[0].message.content,
        "total_time_ms": round(elapsed * 1000),
        "time_to_first_token_ms": round(elapsed * 1000),  # Same as total (no streaming)
        "tokens": response.usage.total_tokens,
        "mode": "non-streaming",
    }


# --- Streaming endpoint ---

@app.post("/chat/stream")
async def chat_streaming(request: ChatRequest):
    """SSE streaming response. Tokens arrive as they're generated."""
    start = time.time()
    first_token_time = None

    def generate():
        nonlocal first_token_time

        stream = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": request.message}],
            max_tokens=request.max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                if first_token_time is None:
                    first_token_time = time.time()
                    ttft = round((first_token_time - start) * 1000)
                    yield f"data: {json.dumps({'type': 'meta', 'time_to_first_token_ms': ttft})}\n\n"

                token = chunk.choices[0].delta.content
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        total_time = round((time.time() - start) * 1000)
        yield f"data: {json.dumps({'type': 'done', 'total_time_ms': total_time})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# --- Comparison endpoint ---

@app.get("/compare")
async def compare(prompt: str = Query(default="Explain what streaming means in web APIs in 3 paragraphs.")):
    """Run both modes and compare timing."""
    # Non-streaming
    start = time.time()
    response_full = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )
    non_stream_time = round((time.time() - start) * 1000)

    # Streaming (measure time-to-first-token)
    start = time.time()
    first_token_time = None
    full_response = ""

    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            if first_token_time is None:
                first_token_time = time.time()
            full_response += chunk.choices[0].delta.content

    stream_total_time = round((time.time() - start) * 1000)
    ttft = round((first_token_time - start) * 1000) if first_token_time else 0

    return {
        "prompt": prompt,
        "non_streaming": {
            "total_time_ms": non_stream_time,
            "time_to_first_token_ms": non_stream_time,
            "user_waits_ms": non_stream_time,
        },
        "streaming": {
            "total_time_ms": stream_total_time,
            "time_to_first_token_ms": ttft,
            "user_waits_ms": ttft,
        },
        "improvement": f"User sees content {non_stream_time - ttft}ms earlier with streaming",
        "ttft_ratio": f"{non_stream_time / max(ttft, 1):.1f}x faster perceived response",
    }


# --- HTML Client ---

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Streaming Demo</title>
    <style>
        body { font-family: monospace; max-width: 800px; margin: 40px auto; padding: 0 20px; }
        .response { background: #f4f4f4; padding: 15px; margin: 10px 0; min-height: 50px; white-space: pre-wrap; }
        button { padding: 10px 20px; margin: 5px; cursor: pointer; }
        .timing { color: #666; font-size: 0.9em; }
    </style>
    </head>
    <body>
        <h1>Streaming vs Non-Streaming Demo</h1>
        <input id="prompt" type="text" value="Write a short poem about programming." style="width:100%; padding:10px; font-size:16px;">
        <br><br>
        <button onclick="sendNonStreaming()">Non-Streaming</button>
        <button onclick="sendStreaming()">Streaming (SSE)</button>
        <button onclick="sendBoth()">Compare Both</button>

        <h3>Non-Streaming Response:</h3>
        <div class="response" id="non-stream-output">Waiting...</div>
        <div class="timing" id="non-stream-timing"></div>

        <h3>Streaming Response:</h3>
        <div class="response" id="stream-output">Waiting...</div>
        <div class="timing" id="stream-timing"></div>

        <script>
        async function sendNonStreaming() {
            const prompt = document.getElementById('prompt').value;
            const output = document.getElementById('non-stream-output');
            const timing = document.getElementById('non-stream-timing');
            output.textContent = 'Loading...';
            const start = Date.now();

            const res = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: prompt})
            });
            const data = await res.json();
            output.textContent = data.response;
            timing.textContent = `Total: ${data.total_time_ms}ms | User waited: ${data.total_time_ms}ms for ANY content`;
        }

        async function sendStreaming() {
            const prompt = document.getElementById('prompt').value;
            const output = document.getElementById('stream-output');
            const timing = document.getElementById('stream-timing');
            output.textContent = '';
            const start = Date.now();
            let firstTokenTime = null;

            const res = await fetch('/chat/stream', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: prompt})
            });

            const reader = res.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                const text = decoder.decode(value);
                const lines = text.split('\\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        if (data.type === 'token') {
                            if (!firstTokenTime) firstTokenTime = Date.now();
                            output.textContent += data.content;
                        } else if (data.type === 'done') {
                            timing.textContent = `TTFT: ${firstTokenTime - start}ms | Total: ${data.total_time_ms}ms | User saw content ${data.total_time_ms - (firstTokenTime - start)}ms EARLIER`;
                        }
                    }
                }
            }
        }

        function sendBoth() { sendNonStreaming(); sendStreaming(); }
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    print("\n  Starting Streaming Basics Demo Server")
    print("  Open http://localhost:8000 in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
