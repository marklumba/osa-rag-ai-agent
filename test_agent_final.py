import vertexai
from vertexai.preview import reasoning_engines

# Initialize Vertex AI
vertexai.init(project="osa-rag-ai-agent", location="asia-southeast1")

# Load your deployed agent
agent_id = "projects/13058804497/locations/asia-southeast1/reasoningEngines/1421044012109791232"
agent = reasoning_engines.ReasoningEngine(agent_id)

print("✅ Agent loaded successfully!")
print(f"   Display name: {agent.display_name}")
print(f"   Resource: {agent.resource_name}")

# Create a session with user_id
print("\n🔄 Creating session...")
try:
    session = agent.create_session(user_id="test-user")
    print(f"✅ Session created: {session.name}")
    
    # Now try to send a message
    print("\n💬 Sending test message...")
    # The actual query method might be different - let's see what's available
    print(f"   Available session methods: {[m for m in dir(session) if not m.startswith('_')]}")
    
except Exception as e:
    print(f"❌ Error: {e}")