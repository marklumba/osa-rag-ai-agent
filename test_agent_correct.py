import vertexai
from vertexai.preview import reasoning_engines

# Initialize Vertex AI
vertexai.init(project="osa-rag-ai-agent", location="asia-southeast1")

# Load your deployed agent
agent_id = "projects/13058804497/locations/asia-southeast1/reasoningEngines/1421044012109791232"
agent = reasoning_engines.ReasoningEngine(agent_id)

print("Testing agent...")
print(f"Agent loaded: {agent.resource_name}")
print(f"Display name: {agent.display_name}")
print(f"State: Active")

# Create a session
print("\nCreating session...")
session = agent.create_session()
print(f"Session created: {session.name}")

# Try to query through the session
print("\nSending query...")
try:
    # The session should have methods to interact with the agent
    response = session.query(input="Hello, what can you help me with?")
    print("Success! Response:")
    print(response)
except AttributeError:
    print("Session methods available:")
    print([m for m in dir(session) if not m.startswith('_')])
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    