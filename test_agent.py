import vertexai
from vertexai.preview import reasoning_engines

# Initialize Vertex AI
vertexai.init(project="osa-rag-ai-agent", location="asia-southeast1")

# Load your deployed agent
agent = reasoning_engines.ReasoningEngine(
    "projects/13058804497/locations/asia-southeast1/reasoningEngines/1421044012109791232"
)

# Test the agent - use the correct method
print("Testing agent...")
try:
    # Try the standard invocation
    response = agent.invoke(input="Hello, what can you help me with?")
    print("Response:", response)
except Exception as e:
    print(f"Error: {e}")
    # Try alternative method
    print("Trying alternative method...")
    response = agent.run(input="Hello, what can you help me with?")
    print("Response:", response)
