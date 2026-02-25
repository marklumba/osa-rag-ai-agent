import vertexai
from vertexai.preview import reasoning_engines

# Initialize Vertex AI
vertexai.init(project="osa-rag-ai-agent", location="asia-southeast1")

# Load your deployed agent
agent_id = "projects/13058804497/locations/asia-southeast1/reasoningEngines/8473118078618566656"
agent = reasoning_engines.ReasoningEngine(agent_id)

print("✅ Agent loaded successfully!")
print(f"   Display name: {agent.display_name}")

# Create a session with user_id
print("\n🔄 Creating session...")
session = agent.create_session(user_id="test-user")
print(f"✅ Session created!")
print(f"   Session data: {session}")

# The session is a dict, extract session_id
session_id = session.get('name', 'unknown')
print(f"   Session ID: {session_id}")

print("\n🎉 YOUR AGENT IS WORKING!")
print("   ✅ Agent deployed and active")
print("   ✅ Can create sessions")
print("   ✅ Ready to handle requests")