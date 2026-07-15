import anthropic

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=20,
    messages=[
        {
            "role": "user",
            "content": "Reply with exactly: API works"
        }
    ]
)

print(response.content[0].text)

