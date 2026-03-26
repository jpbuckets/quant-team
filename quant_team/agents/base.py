"""Base agent class wrapping the Claude API."""

from __future__ import annotations

import asyncio

import anthropic
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str  # agent name or "system"
    content: str


class Agent:
    """A specialist agent on the trading desk, powered by Claude."""

    def __init__(
        self,
        name: str,
        title: str,
        system_prompt: str,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.name = name
        self.title = title
        self.system_prompt = system_prompt
        self.model = model
        self.client = anthropic.AsyncAnthropic()
        self.memory: list[Message] = []

    async def analyze(
        self,
        market_context: str,
        discussion: list[Message] | None = None,
        task: str = "",
    ) -> str:
        """Have this agent analyze data and contribute to the discussion."""
        messages = []

        # Build the user message with market context and prior discussion
        parts = []
        if task:
            parts.append(f"## Task\n{task}")
        parts.append(f"## Market Data & Indicators\n{market_context}")

        if discussion:
            parts.append("## Team Discussion So Far")
            for msg in discussion:
                parts.append(f"**{msg.role}**: {msg.content}")

        # Include agent's own memory of past sessions
        if self.memory:
            parts.append("## Your Notes from Previous Sessions")
            for mem in self.memory[-5:]:  # last 5 memories
                parts.append(mem.content)

        messages.append({"role": "user", "content": "\n\n".join(parts)})

        response = await asyncio.wait_for(
            self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                messages=messages,
            ),
            timeout=300.0,
        )

        result = response.content[0].text
        self.memory.append(Message(role=self.name, content=result))
        return result

    async def respond(self, prompt: str) -> str:
        """Simple single-turn response for IPS drafting, etc."""
        response = await asyncio.wait_for(
            self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=300.0,
        )
        return response.content[0].text

    def __repr__(self) -> str:
        return f"Agent({self.name!r}, {self.title!r})"
