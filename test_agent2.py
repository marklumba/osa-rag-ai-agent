import vertexai
from vertexai.preview import reasoning_engines

# Initialize Vertex AI
vertexai.init(project="osa-rag-ai-agent", location="asia-southeast1")

# Load your deployed agent
agent_id = "projects/13058804497/locations/asia-southeast1/reasoningEngines/1421044012109791232"
agent = reasoning_engines.ReasoningEngine(agent_id)

# Test the agent
print("Testing agent...")
print(f"Agent loaded: {agent.resource_name}")

# Try to call the agent
try:
    result = agent.query(input="Hello, what can you help me with?")
    print("Success! Response:")
    print(result)
except AttributeError as e:
    print(f"Method 'query' not available. Trying alternatives...")
    print(f"Available methods: {[m for m in dir(agent) if not m.startswith('_')]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")