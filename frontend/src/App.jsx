import { useState, useEffect, useRef, useCallback } from 'react';
import { jsPDF } from 'jspdf';

// ─── Design tokens ─────────────────────────────────────────────────────────
const C = {
  black:      '#0a0a0a',
  darkGrey:   '#1a1a1a',
  panelGrey:  '#141414',
  midGrey:    '#262626',
  lightGrey:  '#737373',
  uiAccent:   '#a3a3a3',
  white:      '#f5f5f5',
  green:      '#22c55e',
  greenDim:   '#14532d',
  danger:     '#ef4444',
  dangerDim:  '#7f1d1d',
  amber:      '#f59e0b',
  amberDim:   '#78350f',
  cyan:       '#22d3ee',
};

const FONT = "'JetBrains Mono', monospace";
const MAX_LOGS = 500;
const WS_URL  = 'ws://127.0.0.1:8000/ws';
const API_URL = 'http://127.0.0.1:8000';

// ─── Helpers ────────────────────────────────────────────────────────────────
function useSessionTimer(running) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(null);

  useEffect(() => {
    if (running) {
      startRef.current = Date.now() - elapsed * 1000;
      const id = setInterval(
        () => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)),
        1000
      );
      return () => clearInterval(id);
    }
  }, [running]); // eslint-disable-line react-hooks/exhaustive-deps

  const fmt = (s) => {
    const h = String(Math.floor(s / 3600)).padStart(2, '0');
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
    const sec = String(s % 60).padStart(2, '0');
    return `${h}:${m}:${sec}`;
  };

  return fmt(elapsed);
}

// ─── Main component ─────────────────────────────────────────────────────────
function App() {
  const [isSystemStarted, setIsSystemStarted] = useState(false);
  const [isFeedActive,    setIsFeedActive]    = useState(false);
  const [telemetry,       setTelemetry]       = useState([]);
  const [fullLogs,        setFullLogs]        = useState([]);
  const [fps,             setFps]             = useState(0);
  const [isConnected,     setIsConnected]     = useState(false);
  const [detectionCount,  setDetectionCount]  = useState(0);

  const displayImageRef = useRef(null);
  const lastFrameTime   = useRef(null); // initialised on first frame to avoid Date.now() in render
  const sessionTime     = useSessionTimer(isSystemStarted);

  // ── WebSocket lifecycle ──────────────────────────────────────────────────
  useEffect(() => {
    if (!isSystemStarted) return;

    const ws = new WebSocket(WS_URL);

    ws.onopen  = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);
    ws.onerror = () => setIsConnected(false);

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return; // Discard malformed frames
      }

      // Update live video feed via direct DOM mutation (bypasses React reconciler)
      if (data.image && displayImageRef.current) {
        displayImageRef.current.src = 'data:image/jpeg;base64,' + data.image;
      }

      // Update FPS counter
      const now = Date.now();
      if (lastFrameTime.current !== null) {
        setFps(Math.round(1000 / (now - lastFrameTime.current)));
      }
      lastFrameTime.current = now;

      // Update telemetry sidebar + persistent log
      if (data.telemetry && data.telemetry.length > 0) {
        setDetectionCount((c) => c + data.telemetry.length);

        setTelemetry((prev) =>
          [...new Set([...data.telemetry, ...prev])].slice(0, 10)
        );

        const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
        setFullLogs((prev) => {
          const newEntries = data.telemetry.map((d) => `[${timestamp}] ${d}`);
          // Deduplicate and cap at MAX_LOGS entries to prevent memory growth
          const merged = [...newEntries, ...prev];
          const unique = [...new Set(merged)];
          return unique.slice(0, MAX_LOGS);
        });
      }
    };

    return () => ws.close();
  }, [isSystemStarted]);

  // ── Control handlers ────────────────────────────────────────────────────
  const handleInitialize = useCallback(async () => {
    setIsSystemStarted(true);
    setIsFeedActive(true);
    await fetch(`${API_URL}/start-feed`, { method: 'POST' }).catch(() => {});
  }, []);

  const handleToggleFeed = useCallback(async () => {
    if (isFeedActive) {
      await fetch(`${API_URL}/stop-feed`, { method: 'POST' }).catch(() => {});
      setIsFeedActive(false);
    } else {
      await fetch(`${API_URL}/start-feed`, { method: 'POST' }).catch(() => {});
      setIsFeedActive(true);
    }
  }, [isFeedActive]);

  const handleExportPDF = useCallback(() => {
    const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const pageW = doc.internal.pageSize.getWidth();
    const margin = 15;
    const lineH  = 6;
    let y = margin;

    // ── Header ──
    doc.setFont('courier', 'bold');
    doc.setFontSize(16);
    doc.setTextColor(30, 30, 30);
    doc.text('WINGID // INTEL DOSSIER', margin, y);
    y += 8;

    doc.setFontSize(9);
    doc.setFont('courier', 'normal');
    doc.setTextColor(100, 100, 100);
    doc.text(
      `Generated: ${new Date().toUTCString()}  |  Session: ${sessionTime}  |  Detections: ${detectionCount}`,
      margin, y
    );
    y += 4;
    doc.setDrawColor(60, 60, 60);
    doc.line(margin, y, pageW - margin, y);
    y += 8;

    // ── Log entries ──
    doc.setFont('courier', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(20, 20, 20);

    if (fullLogs.length === 0) {
      doc.text('No detections recorded this session.', margin, y);
    } else {
      fullLogs.forEach((entry) => {
        if (y > 280) {
          doc.addPage();
          y = margin;
        }
        doc.text(entry, margin, y);
        y += lineH;
      });
    }

    // ── Footer ──
    const totalPages = doc.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      doc.setFontSize(7);
      doc.setTextColor(150, 150, 150);
      doc.text(
        `WingID Intel Dossier  |  Page ${i} of ${totalPages}`,
        margin,
        doc.internal.pageSize.getHeight() - 8
      );
    }

    doc.save(`wingid_intel_${Date.now()}.pdf`);
  }, [fullLogs, detectionCount, sessionTime]);

  // ── Derived state ────────────────────────────────────────────────────────
  const trackerStatus = !isSystemStarted
    ? 'STANDBY'
    : isFeedActive
    ? 'TRACKING_ACTIVE'
    : 'FEED_SUSPENDED';

  const statusColor = !isSystemStarted
    ? C.lightGrey
    : isFeedActive && isConnected
    ? C.green
    : C.amber;

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div style={{
      backgroundColor: C.black,
      backgroundImage: `
        linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)
      `,
      backgroundSize: '40px 40px',
      height: '100vh',
      width: '100vw',
      padding: '20px',
      boxSizing: 'border-box',
      color: C.white,
      fontFamily: FONT,
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
    }}>

      {/* ── Header ── */}
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: `1px solid ${C.midGrey}`,
        paddingBottom: '14px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontWeight: 900, letterSpacing: '6px', fontSize: '18px', color: C.white }}>
            WINGID
          </span>
          <span style={{ color: C.lightGrey, fontSize: '11px', letterSpacing: '2px' }}>
            // AEROSPACE TELEMETRY COMMAND CENTER
          </span>
        </div>
        <div style={{ display: 'flex', gap: '24px', fontSize: '11px', fontWeight: 'bold', alignItems: 'center' }}>
          <span style={{ color: C.lightGrey }}>SESSION {sessionTime}</span>
          <span style={{ color: C.lightGrey }}>DET: {detectionCount}</span>
          <span style={{ color: C.lightGrey }}>FPS: <span style={{ color: C.white }}>{fps}</span></span>
          <span style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            color: isConnected ? C.green : C.danger,
          }}>
            <span style={{
              width: '7px', height: '7px', borderRadius: '50%',
              backgroundColor: isConnected ? C.green : C.danger,
              boxShadow: isConnected ? `0 0 6px ${C.green}` : 'none',
              display: 'inline-block',
            }} />
            {isConnected ? 'DATALINK_SECURED' : 'LINK_LOST'}
          </span>
        </div>
      </header>

      {/* ── Main grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: '16px', flex: 1, minHeight: 0 }}>

        {/* ── Vision panel ── */}
        <div style={{
          border: `1px solid ${C.midGrey}`,
          backgroundColor: C.panelGrey,
          display: 'flex',
          flexDirection: 'column',
          borderRadius: '4px',
          overflow: 'hidden',
        }}>
          {/* Panel header */}
          <div style={{
            padding: '10px 14px',
            borderBottom: `1px solid ${C.midGrey}`,
            fontSize: '11px',
            fontWeight: 900,
            letterSpacing: '2px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: C.darkGrey,
          }}>
            <span style={{ color: C.uiAccent }}>AEROSPACE_VISION_TRACKER</span>
            <span style={{ color: statusColor, fontSize: '10px' }}>● {trackerStatus}</span>
          </div>

          {/* Feed area */}
          <div style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            overflow: 'hidden',
            backgroundColor: '#050505',
          }}>
            {!isSystemStarted ? (
              <div style={{ textAlign: 'center' }}>
                <div style={{ color: C.lightGrey, fontSize: '11px', letterSpacing: '3px', marginBottom: '24px' }}>
                  SYSTEM STANDBY — SENSORS OFFLINE
                </div>
                <button
                  id="btn-initialize"
                  onClick={handleInitialize}
                  style={{
                    padding: '16px 48px',
                    backgroundColor: 'transparent',
                    border: `1px solid ${C.white}`,
                    color: C.white,
                    fontSize: '14px',
                    cursor: 'pointer',
                    fontWeight: 900,
                    letterSpacing: '4px',
                    fontFamily: FONT,
                    textTransform: 'uppercase',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = C.white;
                    e.currentTarget.style.color = C.black;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                    e.currentTarget.style.color = C.white;
                  }}
                >
                  INITIALIZE SENSORS
                </button>
              </div>
            ) : (
              <div style={{ width: '100%', height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column' }}>
                {!isConnected && (
                  <div style={{ color: C.amber, fontSize: '13px', fontWeight: 'bold', letterSpacing: '3px', textAlign: 'center' }}>
                    ◌ WAITING FOR SYSTEM HANDSHAKE...
                  </div>
                )}
                {isConnected && !isFeedActive && (
                  <div style={{ color: C.lightGrey, fontSize: '14px', fontWeight: 'bold', letterSpacing: '3px', textAlign: 'center' }}>
                    ⏸ FEED SUSPENDED
                  </div>
                )}
                <img
                  ref={displayImageRef}
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    display: isConnected && isFeedActive ? 'block' : 'none',
                  }}
                  alt="Live aerospace tracking feed"
                />
              </div>
            )}
          </div>

          {/* Toggle feed button */}
          {isSystemStarted && (
            <div style={{ borderTop: `1px solid ${C.midGrey}`, padding: '10px 14px', backgroundColor: C.darkGrey }}>
              <button
                id="btn-toggle-feed"
                onClick={handleToggleFeed}
                style={{
                  width: '100%',
                  padding: '12px',
                  backgroundColor: isFeedActive ? C.dangerDim : C.greenDim,
                  border: `1px solid ${isFeedActive ? C.danger : C.green}`,
                  color: isFeedActive ? C.danger : C.green,
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 900,
                  letterSpacing: '3px',
                  fontFamily: FONT,
                  transition: 'all 0.15s ease',
                  borderRadius: '2px',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.75'; }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
              >
                {isFeedActive ? '■  TERMINATE FEED' : '▶  RESUME FEED'}
              </button>
            </div>
          )}
        </div>

        {/* ── Right sidebar ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', minHeight: 0 }}>

          {/* Live detections */}
          <div style={{
            border: `1px solid ${C.midGrey}`,
            backgroundColor: C.panelGrey,
            display: 'flex',
            flexDirection: 'column',
            flex: '0 0 auto',
            borderRadius: '4px',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '10px 14px',
              borderBottom: `1px solid ${C.midGrey}`,
              fontSize: '11px',
              fontWeight: 900,
              letterSpacing: '2px',
              color: C.uiAccent,
              backgroundColor: C.darkGrey,
            }}>
              LIVE_DETECTIONS
            </div>
            <div style={{
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              maxHeight: '200px',
              overflowY: 'auto',
              fontSize: '10px',
            }}>
              {telemetry.length === 0 ? (
                <span style={{ color: C.lightGrey, letterSpacing: '1px' }}>SCANNING HORIZON...</span>
              ) : (
                telemetry.map((d, i) => (
                  <div key={i} style={{
                    color: C.cyan,
                    borderLeft: `2px solid ${C.cyan}`,
                    backgroundColor: 'rgba(34,211,238,0.05)',
                    padding: '6px 8px',
                    borderRadius: '2px',
                    fontWeight: 'bold',
                    lineHeight: '1.4',
                  }}>
                    {d}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Combat log */}
          <div style={{
            border: `1px solid ${C.midGrey}`,
            backgroundColor: C.panelGrey,
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            minHeight: 0,
            borderRadius: '4px',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '10px 14px',
              borderBottom: `1px solid ${C.midGrey}`,
              fontSize: '11px',
              fontWeight: 900,
              letterSpacing: '2px',
              color: C.uiAccent,
              backgroundColor: C.darkGrey,
              display: 'flex',
              justifyContent: 'space-between',
            }}>
              <span>COMBAT_LOG</span>
              <span style={{ color: C.lightGrey, fontSize: '10px' }}>{fullLogs.length}/{MAX_LOGS}</span>
            </div>
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}>
              {fullLogs.length === 0 ? (
                <span style={{ color: C.lightGrey, fontSize: '10px' }}>No events logged yet.</span>
              ) : (
                fullLogs.map((entry, i) => (
                  <div key={i} style={{ fontSize: '9px', color: C.lightGrey, lineHeight: '1.6', fontFamily: FONT }}>
                    {entry}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Export button */}
          <button
            id="btn-export-intel"
            onClick={handleExportPDF}
            disabled={fullLogs.length === 0}
            style={{
              padding: '14px',
              backgroundColor: fullLogs.length > 0 ? C.midGrey : C.darkGrey,
              border: `1px solid ${fullLogs.length > 0 ? C.uiAccent : C.midGrey}`,
              color: fullLogs.length > 0 ? C.white : C.lightGrey,
              cursor: fullLogs.length > 0 ? 'pointer' : 'not-allowed',
              fontSize: '11px',
              fontWeight: 900,
              letterSpacing: '2px',
              fontFamily: FONT,
              borderRadius: '2px',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => { if (fullLogs.length > 0) e.currentTarget.style.backgroundColor = C.lightGrey; }}
            onMouseLeave={(e) => { if (fullLogs.length > 0) e.currentTarget.style.backgroundColor = C.midGrey; }}
          >
            ↓  DUMP TRACKING INTEL
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
