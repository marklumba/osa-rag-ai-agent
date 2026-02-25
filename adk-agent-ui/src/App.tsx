import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Upload, Bot, Loader2, User, Copy, Check, Share2 } from 'lucide-react';
import './App.css';
import LightweightRenderer from './components/lightweight-renderer';


interface Message {
  id: string;
  text: string;
  sender: 'user' | 'agent';
  timestamp: Date;
}

interface AgentStatus {
  status: string;
  loaded_dataframes: string[];
  dataframe_count: number;
}

// Generate a stable session ID for the entire browser session
// This persists as long as the tab is open
const SESSION_ID = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
const USER_ID = 'default-user';

const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: "🤖 Hello! I'm your OSA ADK Hybrid RAG AI Agent. I can help you with BOTH document search (RAG) and structured data analysis (Pandas).\n\n📂 RAG Corpus Tools:\n- list_corpora\n- create_corpus\n- add_data\n- get_corpus_info\n- rag_query\n- delete_corpus\n- delete_document\n\n📊 Structured Data Tools:\n- load_dataframe\n- query_dataframe\n- list_dataframes\n- execute_pandas_code\n- compare_dataframes\n\n👉 Try running one of these tools, or paste a Google Drive/Excel/CSV URL to get started!\n\n⚠️ Note: Loaded dataframes are remembered within your current session. If you refresh the page, you'll need to reload your files.",
      sender: 'agent',
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [sharedMessageId, setSharedMessageId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // const API_BASE = 'https://rag-backend-3213124214.asia-southeast1.run.app';
  // const LOCAL_API_BASE = 'http://localhost:8000';

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    fetchAgentStatus();
    // Log session info for debugging
    console.log(`Session ID: ${SESSION_ID}`);
    console.log(`User ID: ${USER_ID}`);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchAgentStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/status`);
      setAgentStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch agent status:', error);
    }
  };

  const copyToClipboard = async (text: string, messageId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const shareMessage = async (message: Message) => {
    const shareData = {
      title: 'OSA ADK AI Agent Response',
      text: message.text,
    };

    try {
      if (navigator.share) {
        await navigator.share(shareData);
        setSharedMessageId(message.id);
        setTimeout(() => setSharedMessageId(null), 2000);
      } else {
        const formattedText = `📱 Shared from OSA ADK AI Agent\n\n${message.text}\n\n⏰ ${message.timestamp.toLocaleString()}`;
        await navigator.clipboard.writeText(formattedText);
        setSharedMessageId(message.id);
        setTimeout(() => setSharedMessageId(null), 2000);
      }
    } catch (error) {
      console.error('Failed to share:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputText.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputText,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/api/chat`, {
        message: inputText,
        session_id: SESSION_ID,   // ✅ Stable session ID for entire tab session
        user_id: USER_ID
      });

      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.data.response || 'No response received.',
        sender: 'agent',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, agentMessage]);
      fetchAgentStatus();

    } catch (error: any) {
      console.error('Chat error:', error);

      // Better error message - don't mention localhost
      const errorText = error?.response?.data?.detail
        || error?.response?.data?.response
        || error?.message
        || 'An unexpected error occurred. Please try again.';

      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: `❌ Error: ${errorText}`,
        sender: 'agent',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_BASE}/api/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const message: Message = {
        id: Date.now().toString(),
        text: `📎 File uploaded: ${file.name}\nPath: ${response.data.file_path}\n\nYou can now reference this file in your queries!`,
        sender: 'agent',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, message]);
    } catch (error) {
      const errorMessage: Message = {
        id: Date.now().toString(),
        text: `❌ Failed to upload file: ${file.name}`,
        sender: 'agent',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-title">
            <Bot className="header-icon" />
            <h1>OSA ADK Hybrid RAG AI Agent</h1>
          </div>
          <div className="agent-status">
            {agentStatus && (
              <div className="status-info">
                <span className={`status-dot ${agentStatus.status === 'ready' ? 'ready' : 'error'}`}></span>
                <span>Agent Ready</span>
                {agentStatus.dataframe_count > 0 && (
                  <span className="data-count">• {agentStatus.dataframe_count} datasets loaded</span>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="chat-container">
        <div className="messages">
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.sender}`}>
              {/* Avatar */}
              <div className="message-avatar">
                {message.sender === 'agent' ? <Bot size={24} /> : <User size={24} />}
              </div>
              
              {/* Message Content */}
              <div className="message-content">
                {message.sender === 'agent' ? (
                  <div className="message-text">
                    <LightweightRenderer content={message.text} />
                  </div>
                ) : (
                  <div className="message-text">{message.text}</div>
                )}
                
                <div className="message-footer">
                  <div className="message-time">
                    {message.timestamp.toLocaleTimeString()}
                  </div>
                  <div className="message-actions">
                    <button
                      onClick={() => copyToClipboard(message.text, message.id)}
                      className="action-icon-button"
                      title="Copy message"
                    >
                      {copiedMessageId === message.id ? (
                        <Check size={30} className="action-icon success" />
                      ) : (
                        <Copy size={30} className="action-icon" />
                      )}
                    </button>
                    <button
                      onClick={() => shareMessage(message)}
                      className="action-icon-button"
                      title="Share message"
                    >
                      {sharedMessageId === message.id ? (
                        <Check size={30} className="action-icon success" />
                      ) : (
                        <Share2 size={30} className="action-icon" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message agent">
              <div className="message-avatar">
                <Bot size={24} />
              </div>
              <div className="message-content">
                <div className="message-text loading">
                  <Loader2 className="spinner" size={16} />
                  Processing...
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <div className="input-wrapper">
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask me about documents, load data from Google Drive, or analyze your datasets..."
              className="message-input"
              rows={3}
              disabled={isLoading}
            />
            <div className="input-actions">
              <button
                className="action-btn upload-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
                title="Upload file"
              >
                <Upload size={22} />
              </button>
              <button
                className="action-btn send-btn"
                onClick={sendMessage}
                disabled={!inputText.trim() || isLoading}
                title="Send message"
              >
                <Send size={22} />
              </button>
            </div>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileUpload}
            style={{ display: 'none' }}
            accept=".csv,.xlsx,.xls,.json,.pdf,.txt"
          />
        </div>
      </main>
    </div>
  );
};

export default App;
