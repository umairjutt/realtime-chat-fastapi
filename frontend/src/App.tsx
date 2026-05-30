import { useEffect, useRef, useState } from 'react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

type Msg = { type: 'message'; user: string; text: string; ts: string };
type Presence = { type: 'presence'; online: string[] };

export function App() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState('alice');
  const [password, setPassword] = useState('password');
  const [roomId] = useState(1);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [online, setOnline] = useState<string[]>([]);
  const [draft, setDraft] = useState('');
  const ws = useRef<WebSocket | null>(null);

  async function login() {
    const r = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const d = await r.json();
    setToken(d.token);
  }

  useEffect(() => {
    if (!token) return;

    fetch(`${API}/rooms/${roomId}/messages`).then(r => r.json()).then(setMessages);

    const sock = new WebSocket(`${WS}/ws/${roomId}?token=${token}`);
    sock.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'message') setMessages((m) => [...m, data]);
      else if (data.type === 'presence') setOnline((data as Presence).online);
    };
    ws.current = sock;
    return () => sock.close();
  }, [token, roomId]);

  function send() {
    if (!draft.trim() || !ws.current) return;
    ws.current.send(JSON.stringify({ type: 'message', text: draft }));
    setDraft('');
  }

  if (!token) {
    return (
      <div style={{ maxWidth: 320, margin: '80px auto', padding: 24 }}>
        <h2>Login</h2>
        <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" />{' '}
        <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" type="password" />{' '}
        <button onClick={login}>Login</button>
        <p style={{ opacity: 0.6, fontSize: 13 }}>Try alice / bob / charlie (password: password). Open in two tabs.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', height: '100vh' }}>
      <aside style={{ borderRight: '1px solid #30363d', padding: 16 }}>
        <h3>Online</h3>
        <ul>{online.map((u) => <li key={u}>{u}</li>)}</ul>
      </aside>
      <main style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {messages.map((m, i) => (
            <div key={i} style={{ marginBottom: 8 }}>
              <strong style={{ color: m.user === username ? '#58a6ff' : '#e6edf3' }}>{m.user}</strong>: {m.text}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', padding: 16, gap: 8, borderTop: '1px solid #30363d' }}>
          <input
            style={{ flex: 1 }}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder="Type a message..."
          />
          <button onClick={send}>Send</button>
        </div>
      </main>
    </div>
  );
}
