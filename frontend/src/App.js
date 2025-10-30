import { useState, useEffect, useRef } from "react";
import "@/App.css";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Loader2, Send, Globe, Leaf, CloudRain, ExternalLink, BarChart3 } from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [language, setLanguage] = useState("en");
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Generate session ID on mount
    setSessionId(`session-${Date.now()}`);
  }, []);

  useEffect(() => {
    // Scroll to bottom when messages change
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      role: "user",
      content: input,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await axios.post(`${API}/chat/query`, {
        question: input,
        session_id: sessionId,
        language: language
      });

      const assistantMessage = {
        role: "assistant",
        content: response.data.answer,
        sources: response.data.sources || [],
        timestamp: response.data.timestamp
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error sending message:", error);
      toast.error(language === "hi" ? "त्रुटि: संदेश भेजने में विफल" : "Error: Failed to send message");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const exampleQueries = language === "en" ? [
    "What are the top rice producing states in India?",
    "Show rainfall trends in Maharashtra",
    "Compare crop yields between 2020 and 2022"
  ] : [
    "भारत में सर्वाधिक चावल उत्पादक राज्य कौन से हैं?",
    "महाराष्ट्र में वर्षा के रुझान दिखाएं",
    "2020 और 2022 के बीच फसल उपज की तुलना करें"
  ];

  return (
    <div className="app-container" data-testid="app-container">
      {/* Header */}
      <header className="app-header" data-testid="app-header">
        <div className="header-content">
          <div className="header-left">
            <div className="logo-section">
              <div className="logo-icon">
                <Leaf className="icon" />
                <CloudRain className="icon icon-overlay" />
              </div>
              <div>
                <h1 className="app-title" data-testid="app-title">
                  {language === "en" ? "AgriClimate Intelligence" : "कृषि जलवायु बुद्धिमत्ता"}
                </h1>
                <p className="app-subtitle">
                  {language === "en" 
                    ? "Natural Language Q&A for India's Agricultural & Climate Data"
                    : "भारत के कृषि और जलवायु डेटा के लिए प्राकृतिक भाषा प्रश्नोत्तर"}
                </p>
              </div>
            </div>
          </div>
          <div className="header-right">
            <Button
              data-testid="language-toggle"
              variant="outline"
              size="sm"
              onClick={() => setLanguage(lang => lang === "en" ? "hi" : "en")}
              className="language-btn"
            >
              <Globe className="w-4 h-4 mr-2" />
              {language === "en" ? "हिंदी" : "English"}
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content" data-testid="main-content">
        <div className="chat-container">
          {/* Welcome Screen */}
          {messages.length === 0 && (
            <div className="welcome-screen" data-testid="welcome-screen">
              <div className="welcome-icon">
                <BarChart3 size={64} />
              </div>
              <h2 className="welcome-title">
                {language === "en" 
                  ? "Ask Questions About India's Agriculture & Climate"
                  : "भारत की कृषि और जलवायु के बारे में प्रश्न पूछें"}
              </h2>
              <p className="welcome-desc">
                {language === "en"
                  ? "Get insights from official government datasets with full source traceability"
                  : "पूर्ण स्रोत पता लगाने के साथ आधिकारिक सरकारी डेटासेट से जानकारी प्राप्त करें"}
              </p>
              
              <div className="example-queries">
                <p className="example-label">
                  {language === "en" ? "Try asking:" : "पूछने का प्रयास करें:"}
                </p>
                {exampleQueries.map((query, idx) => (
                  <button
                    key={idx}
                    data-testid={`example-query-${idx}`}
                    className="example-query"
                    onClick={() => setInput(query)}
                  >
                    {query}
                  </button>
                ))}
              </div>

              <div className="data-sources">
                <Badge variant="secondary" className="source-badge">
                  <Leaf className="w-3 h-3 mr-1" />
                  Ministry of Agriculture
                </Badge>
                <Badge variant="secondary" className="source-badge">
                  <CloudRain className="w-3 h-3 mr-1" />
                  India Meteorological Dept
                </Badge>
                <Badge variant="secondary" className="source-badge">
                  <Globe className="w-3 h-3 mr-1" />
                  data.gov.in
                </Badge>
              </div>
            </div>
          )}

          {/* Messages */}
          <div className="messages-container" data-testid="messages-container">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-wrapper ${msg.role}`} data-testid={`message-${idx}`}>
                {msg.role === "user" ? (
                  <div className="user-message">
                    <p>{msg.content}</p>
                  </div>
                ) : (
                  <Card className="assistant-message">
                    <CardContent className="message-content">
                      <div className="answer-text" data-testid={`answer-${idx}`}>
                        {msg.content}
                      </div>
                      
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="sources-section">
                          <Separator className="my-4" />
                          <p className="sources-title">
                            {language === "en" ? "Data Sources:" : "डेटा स्रोत:"}
                          </p>
                          <div className="sources-grid">
                            {msg.sources.map((source, sIdx) => (
                              <a
                                key={sIdx}
                                href={source.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="source-card"
                                data-testid={`source-${idx}-${sIdx}`}
                              >
                                <div>
                                  <p className="source-title">{source.title}</p>
                                  <p className="source-ministry">{source.ministry}</p>
                                  {source.records && (
                                    <p className="source-records">
                                      {source.records} {language === "en" ? "records" : "रिकॉर्ड"}
                                    </p>
                                  )}
                                </div>
                                <ExternalLink className="w-4 h-4" />
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
              </div>
            ))}
            {loading && (
              <div className="message-wrapper assistant" data-testid="loading-indicator">
                <Card className="assistant-message loading-card">
                  <CardContent className="message-content">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>{language === "en" ? "Analyzing data..." : "डेटा का विश्लेषण..."}</span>
                  </CardContent>
                </Card>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="input-container" data-testid="input-container">
          <div className="input-wrapper">
            <Input
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder={language === "en" 
                ? "Ask about agriculture, climate, rainfall, crops..."
                : "कृषि, जलवायु, वर्षा, फसलों के बारे में पूछें..."}
              className="chat-input"
              disabled={loading}
            />
            <Button
              data-testid="send-button"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="send-button"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;