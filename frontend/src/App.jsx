import React, { useState, useEffect, useRef } from 'react';

const colors = {
  baseWhite: '#f5f5f5',
  lightGrey: '#737373',
  darkGrey: '#262626',
  black: '#0a0a0a',
  uiAccent: '#a3a3a3',
  danger: '#ef4444',
  dangerDim: '#7f1d1d',
};

function App() {
  const [isSystemStarted, setIsSystemStarted] = useState(false);
  const [isFeedActive, setIsFeedActive] = useState(false);
  const [telemetry, setTelemetry] = useState([]);
  const [fullLogs, setFullLogs] = useState([]);
  const [fps, setFps] = useState(0);
  const [isConnected, setIsConnected] = useState(false);

  const displayImageRef = useRef(null);
  const lastFrameTime = useRef(Date.now());

  useEffect(() => {
    if (!isSystemStarted) return;

    const ws = new WebSocket('ws://127.0.0.1:8000/ws');

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.image && displayImageRef.current) {
        displayImageRef.current.src = 'data:image/jpeg;base64,' + data.image;
      }

      if (data.telemetry && data.telemetry.length > 0) {
        setTelemetry(prev => [...new Set([...data.telemetry, ...prev])].slice(0, 10));

        const time = new Date().toLocaleTimeString();
        data.telemetry.forEach(d => {
          setFullLogs(prev => {
            const entry = `[${time}] | ${d}`;
            return prev.includes(entry) ? prev : [entry, ...prev];
          });
        });
      }

      const now = Date.now();
      setFps(Math.round(1000 / (now - lastFrameTime.current)));
      lastFrameTime.current = now;
    };

    return () => ws.close();
  }, [isSystemStarted]);

  const handleInitialize = async () => {
    setIsSystemStarted(true);
    setIsFeedActive(true);
    await fetch('http://127.0.0.1:8000/start-feed', { method: 'POST' }).catch(() => {});
  };

  const handleToggleFeed = async () => {
    if (isFeedActive) {
      await fetch('http://127.0.0.1:8000/stop-feed', { method: 'POST' }).catch(() => {});
      setIsFeedActive(false);
    } else {
      await fetch('http://127.0.0.1:8000/start-feed', { method: 'POST' }).catch(() => {});
      setIsFeedActive(true);
    }
  };

  const trackerStatus = !isSystemStarted
    ? 'STANDBY'
    : isFeedActive
    ? 'TRACKING_ACTIVE'
    : 'FEED_SUSPENDED';

  return (
    <div
      style={{
        backgroundColor: colors.black,
        backgroundImage: `linear-gradient(45deg, #121212 25%, transparent 25%, transparent 75%, #121212 75%, #121212), linear-gradient(45deg, #121212 25%, transparent 25%, transparent 75%, #121212 75%, #121212)`,
        backgroundSize: '40px 40px',
        backgroundPosition: '0 0, 20px 20px',
        height: '100vh',
        width: '100vw',
        padding: '24px',
        boxSizing: 'border-box',
        color: colors.baseWhite,
        fontFamily: "'JetBrains Mono', monospace",
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* ── Header ── */}
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          borderBottom: `4px solid ${colors.lightGrey}`,
          backgroundColor: colors.black,
          padding: '16px',
          marginBottom: '24px',
        }}
      >
        <div style={{ fontWeight: '900', letterSpacing: '4px', fontSize: '20px', color: colors.baseWhite }}>
          WINGID_TELEMETRY //<span style={{ color: colors.lightGrey }}> MIL_SPEC</span>
        </div>
        <div style={{ display: 'flex', gap: '20px', fontSize: '13px', fontWeight: 'bold' }}>
          <span style={{ color: colors.lightGrey }}>CHASSIS: SM_12.0</span>
          <span style={{ color: isConnected ? colors.baseWhite : colors.lightGrey }}>
            {isConnected ? '● DATALINK_SECURED' : '● SECURE_LINK_LOST'}
          </span>
          <span style={{ color: colors.baseWhite }}>FPS: {fps}</span>
        </div>
      </header>

      {/* ── Main Grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '24px', flex: 1, minHeight: 0 }}>

        {/* ── Vision Panel ── */}
        <div style={{ border: `4px solid ${colors.darkGrey}`, backgroundColor: colors.black, display: 'flex', flexDirection: 'column' }}>

          {/* Panel header */}
          <div
            style={{
              padding: '12px 16px',
              borderBottom: `4px solid ${colors.darkGrey}`,
              fontSize: '13px',
              color: colors.baseWhite,
              backgroundColor: colors.darkGrey,
              display: 'flex',
              justifyContent: 'space-between',
              fontWeight: '900',
              letterSpacing: '1px',
            }}
          >
            <span>AEROSPACE_VISION_TRACKER</span>
            <span style={{ color: isFeedActive && isConnected ? colors.uiAccent : colors.lightGrey }}>
              {trackerStatus}
            </span>
          </div>

          {/* Feed area */}
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden' }}>
            {!isSystemStarted ? (
              <button
                id="btn-initialize"
                onClick={handleInitialize}
                style={{
                  padding: '20px 50px',
                  backgroundColor: colors.lightGrey,
                  border: `2px solid ${colors.baseWhite}`,
                  color: colors.black,
                  fontSize: '20px',
                  cursor: 'pointer',
                  fontWeight: '900',
                  letterSpacing: '2px',
                  fontFamily: 'inherit',
                  textTransform: 'uppercase',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.backgroundColor = colors.baseWhite; }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = colors.lightGrey; }}
              >
                INITIALIZE SENSORS
              </button>
            ) : (
              <div style={{ width: '100%', height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column' }}>
                {!isConnected && (
                  <div style={{ color: colors.lightGrey, fontSize: '18px', fontWeight: 'bold', letterSpacing: '2px', textAlign: 'center' }}>
                    WAITING FOR SYSTEM HANDSHAKE...
                  </div>
                )}
                {isConnected && !isFeedActive && (
                  <div style={{ color: colors.lightGrey, fontSize: '20px', fontWeight: 'bold', letterSpacing: '2px', textAlign: 'center' }}>
                    ⏸ FEED SUSPENDED
                  </div>
                )}
                <img
                  ref={displayImageRef}
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    zIndex: 10,
                    display: isConnected && isFeedActive ? 'block' : 'none',
                  }}
                  alt=""
                />
              </div>
            )}
          </div>

          {/* ── Toggle Feed Button ── */}
          {isSystemStarted && (
            <div style={{ borderTop: `4px solid ${colors.darkGrey}`, padding: '12px 16px' }}>
              <button
                id="btn-toggle-feed"
                onClick={handleToggleFeed}
                style={{
                  width: '100%',
                  padding: '14px',
                  backgroundColor: isFeedActive ? colors.dangerDim : colors.darkGrey,
                  border: `2px solid ${isFeedActive ? colors.danger : colors.lightGrey}`,
                  color: isFeedActive ? colors.danger : colors.baseWhite,
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: '900',
                  letterSpacing: '2px',
                  fontFamily: 'inherit',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.opacity = '0.8'; }}
                onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
              >
                {isFeedActive ? '■ TERMINATE FEED' : '▶ RESUME FEED'}
              </button>
            </div>
          )}
        </div>

        {/* ── Combat Logs Panel ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ fontSize: '14px', color: colors.baseWhite, marginBottom: '8px', fontWeight: '900', letterSpacing: '2px', backgroundColor: colors.black, padding: '8px' }}>
              // COMBAT_LOGS
            </div>
            <div
              style={{
                border: `4px solid ${colors.darkGrey}`,
                backgroundColor: 'rgba(10, 10, 10, 0.9)',
                flex: 1,
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                overflowY: 'auto',
                fontSize: '12px',
                fontWeight: 'bold',
              }}
            >
              {telemetry.length === 0 && <span style={{ color: colors.lightGrey }}>SCANNING HORIZON...</span>}
              {telemetry.map((d, i) => (
                <div
                  key={i}
                  style={{
                    color: colors.baseWhite,
                    borderLeft: `4px solid ${colors.lightGrey}`,
                    backgroundColor: colors.darkGrey,
                    padding: '8px',
                  }}
                >
                  | {d}
                </div>
              ))}
            </div>
            <button
              onClick={() => {}}
              style={{
                marginTop: '16px',
                padding: '18px',
                backgroundColor: colors.darkGrey,
                border: `2px solid ${colors.lightGrey}`,
                color: colors.baseWhite,
                cursor: 'pointer',
                fontSize: '16px',
                fontWeight: '900',
                letterSpacing: '1px',
                fontFamily: 'inherit',
              }}
            >
              [↓] DUMP TRACKING INTEL
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
