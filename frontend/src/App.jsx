import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';

const API = 'http://localhost:8000';

// ── SVG icons ──────────────────────────────────────────────────────────────
const IconUpload = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const IconFile = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

const IconX = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const IconDown = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const IconDl = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

const IconPlay = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

const IconGrid = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--dim)' }}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M3 9h18M9 21V9" />
  </svg>
);

const IconGlobe = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10z" />
  </svg>
);

// ── Language options matching what the backend supports ──────────────────
const LANGUAGES = [
  { code: 'pl', label: 'Polski (PL)' },
  { code: 'en', label: 'Angielski (EN)' },
  { code: 'de', label: 'Niemiecki (DE)' },
  { code: 'fr', label: 'Francuski (FR)' },
];

const TARGET_LANG_TAGS = ['PL', 'EN', 'DE', 'FR'];

const App = () => {
  const [file, setFile] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [filter, setFilter] = useState('all');
  const [collapsedSections, setCollapsedSections] = useState({});
  const [config, setConfig] = useState({
    source_lang: 'en',
    target_langs: ['en', 'pl'],
    api_type: 'none',
    api_key: '',
  });
  const fileInputRef = useRef(null);

  // ── polling ─────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchTasks();
    const id = setInterval(fetchTasks, 3000);
    return () => clearInterval(id);
  }, []);

  const fetchTasks = async () => {
    try {
      const res = await axios.get(`${API}/tasks`);
      setTasks(res.data);
    } catch (_) { }
  };

  // ── file handling ───────────────────────────────────────────────────────
  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  };

  const handleFileChange = (e) => {
    if (e.target.files?.[0]) setFile(e.target.files[0]);
  };

  // ── target lang toggle ──────────────────────────────────────────────────
  const toggleTargetLang = (code) => {
    const lower = code.toLowerCase();
    setConfig(prev => {
      const has = prev.target_langs.includes(lower);
      if (has && prev.target_langs.length === 1) return prev; // keep at least one
      return {
        ...prev,
        target_langs: has
          ? prev.target_langs.filter(l => l !== lower)
          : [...prev.target_langs, lower],
      };
    });
  };

  // ── submit ──────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!file) return;
    setIsSubmitting(true);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('translate', true);
    fd.append('source_lang', config.source_lang);
    fd.append('target_langs', config.target_langs.join(','));
    fd.append('api_type', config.api_type);
    if (config.api_key) fd.append('api_key', config.api_key);
    try {
      await axios.post(`${API}/tasks`, fd);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchTasks();
    } catch (_) {
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── cancel ──────────────────────────────────────────────────────────────
  const handleCancel = async (id, e) => {
    e.stopPropagation();
    try {
      await axios.post(`${API}/tasks/${id}/cancel`);
      fetchTasks();
    } catch (_) { }
  };

  // ── helpers ─────────────────────────────────────────────────────────────
  const toggleExpand = (id) => setExpanded(p => ({ ...p, [id]: !p[id] }));

  const toggleSection = (n) =>
    setCollapsedSections(p => ({ ...p, [n]: !p[n] }));

  const filteredTasks = tasks.filter(t => {
    if (filter === 'all') return true;
    if (filter === 'processing') return t.status === 'processing' || t.status === 'pending';
    return t.status === filter;
  });

  const runHint = !file
    ? 'Wybierz plik aby kontynuować'
    : config.target_langs.length === 0
      ? 'Wybierz co najmniej jeden język docelowy'
      : '';

  const canRun = !!file && config.target_langs.length > 0 && !isSubmitting;

  // ── render ───────────────────────────────────────────────────────────────
  return (
    <div className="layout">
      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="topbar-logo">
          <div className="logo-mark">M</div>
          <span className="logo-text">Moodle AI</span>
        </div>
      </header>

      {/* ── Sidebar ── */}
      <aside className="sidebar">

        {/* Krok 1: Plik */}
        <div className="sidebar-section">
          <div
            className={`sidebar-section-header active`}
            onClick={() => toggleSection(1)}
          >
            <span className="step-num">1</span>
            Plik źródłowy
          </div>
          {!collapsedSections[1] && (
            <div className="sidebar-section-body">
              <div
                className={`dropzone${file ? ' has-file' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={e => e.preventDefault()}
                onDrop={handleDrop}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".mbz"
                  onChange={handleFileChange}
                />
                <div className="dropzone-icon">
                  <IconUpload />
                </div>
                <div className="dropzone-text">
                  {file ? file.name : <>Przeciągnij plik .mbz<br />lub kliknij aby wybrać</>}
                </div>
                <div className="dropzone-hint">
                  {file ? 'Kliknij aby zmienić plik' : 'Moodle Backup Archive'}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Krok 2: Tłumaczenie */}
        <div className="sidebar-section">
          <div
            className="sidebar-section-header active"
            onClick={() => toggleSection(2)}
          >
            <span className="step-num">2</span>
            Opcje tłumaczenia
          </div>
          {!collapsedSections[2] && (
            <div className="sidebar-section-body">
              <div className="agent-config-section" style={{ borderTop: 'none', marginTop: 0, paddingTop: 0 }}>
                <div className="agent-config-label">
                  <IconGlobe />
                  Konfiguracja języków
                </div>

                <div className="field">
                  <label>Język źródłowy</label>
                  <select
                    value={config.source_lang}
                    onChange={e => setConfig({ ...config, source_lang: e.target.value })}
                  >
                    {LANGUAGES.map(l => (
                      <option key={l.code} value={l.code}>{l.label}</option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label>Języki docelowe</label>
                  <div className="tag-group lang-group">
                    {TARGET_LANG_TAGS.map(tag => (
                      <span
                        key={tag}
                        className={`tag-item${config.target_langs.includes(tag.toLowerCase()) ? ' active' : ''}`}
                        onClick={() => toggleTargetLang(tag)}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Krok 3: Silnik AI */}
        <div className="sidebar-section">
          <div
            className="sidebar-section-header active"
            onClick={() => toggleSection(3)}
          >
            <span className="step-num">3</span>
            Silnik AI
          </div>
          {!collapsedSections[3] && (
            <div className="sidebar-section-body">
              <div className="field">
                <label>Silnik tłumaczenia</label>
                <select
                  value={config.api_type}
                  onChange={e => setConfig({ ...config, api_type: e.target.value })}
                >
                  <option value="none">Mock (bez AI)</option>
                  <option value="openai">OpenAI GPT-4o</option>
                  <option value="deepl">DeepL</option>
                  <option value="gemini">Gemini AI Studio</option>
                </select>
              </div>

              {config.api_type !== 'none' && (
                <div className="field">
                  <label>Klucz API</label>
                  <input
                    type="password"
                    value={config.api_key}
                    onChange={e => setConfig({ ...config, api_key: e.target.value })}
                    placeholder="sk-..."
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sidebar-footer">
          <button
            className="btn-run"
            disabled={!canRun}
            onClick={handleSubmit}
          >
            {isSubmitting
              ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,.2)', borderTopColor: '#fff' }} /> Wysyłanie...</>
              : <><IconPlay /> Uruchom Agenty</>
            }
          </button>
          <div className="run-hint">{runHint}</div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        <div className="task-panel-header">
          <IconGrid />
          <span className="task-panel-title">Monitor Zadań</span>
          <div className="filter-tabs">
            {[
              { key: 'all', label: 'Wszystkie' },
              { key: 'processing', label: 'W toku' },
              { key: 'completed', label: 'Ukończone' },
              { key: 'failed', label: 'Błędy' },
            ].map(f => (
              <button
                key={f.key}
                className={`filter-tab${filter === f.key ? ' active' : ''}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="task-list">
          {filteredTasks.length === 0 ? (
            <div className="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" style={{ opacity: 0.3, color: 'var(--muted)' }}>
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18" />
              </svg>
              <p>Brak zadań w tej kategorii.</p>
            </div>
          ) : (
            filteredTasks.map(task => {
              const isExpanded = expanded[task.id];
              const isActive = task.status === 'processing' || task.status === 'pending';

              let iconEl, iconClass = 'task-icon';
              if (isActive) {
                iconEl = <div className="spinner" />;
                iconClass = 'task-icon';
              } else if (task.status === 'failed') {
                iconEl = <IconX />;
                iconClass = 'task-icon err';
              } else if (task.status === 'cancelled') {
                iconEl = <IconX />;
                iconClass = 'task-icon muted';
              } else {
                iconEl = <IconFile />;
              }

              return (
                <div
                  key={task.id}
                  className={`task-card status-${task.status}${isExpanded ? ' expanded' : ''}`}
                >
                  <div className="task-card-main" onClick={() => toggleExpand(task.id)}>
                    <div className={iconClass} style={isActive ? { background: 'transparent', border: 'none' } : {}}>
                      {iconEl}
                    </div>

                    <div className="task-info">
                      <div className="task-name">{task.original_filename}</div>
                      <div className="task-meta">
                        <span className="task-agent-tag">Tłumaczenie</span>
                        <span style={{ fontSize: '0.62rem', color: 'var(--dim)', fontFamily: 'monospace' }}>
                          #{task.id.split('-')[0]}
                        </span>
                      </div>
                    </div>

                    <div className="task-right">
                      {isActive && (
                        <button
                          className="btn-cancel-task"
                          onClick={(e) => handleCancel(task.id, e)}
                        >
                          Zatrzymaj
                        </button>
                      )}
                      {isActive && (
                        <span style={{ fontSize: '0.72rem', color: 'var(--muted)', fontWeight: 600 }}>
                          Przetwarzanie...
                        </span>
                      )}
                      {task.status === 'failed' && (
                        <span className="badge-error"><IconX /> Błąd</span>
                      )}
                      {task.status === 'cancelled' && (
                        <span className="badge-cancelled">Anulowano</span>
                      )}
                      {task.status === 'completed' && (
                        <a
                          className="btn-dl"
                          href={`${API}/download/${task.id}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={e => e.stopPropagation()}
                        >
                          <IconDl /> Pobierz
                        </a>
                      )}
                      {task.subtasks?.length > 0 && (
                        <span className="expand-arrow"><IconDown /></span>
                      )}
                    </div>
                  </div>

                  {/* Subtasks */}
                  {isExpanded && task.subtasks?.length > 0 && (
                    <div className="task-subtasks" style={{ display: 'flex' }}>
                      {task.subtasks.map((st, i) => {
                        let stIcon;
                        if (st.status === 'processing') stIcon = <div className="spinner-sm" />;
                        else if (st.status === 'completed') stIcon = <span className="subtask-done">✓</span>;
                        else if (st.status === 'failed') stIcon = <span className="subtask-fail">✕</span>;
                        else stIcon = <span className="subtask-done" style={{ opacity: 0.4 }}>−</span>;

                        return (
                          <div key={i} className="subtask-row">
                            {stIcon}
                            <span className="subtask-name">{st.agent}</span>
                            <span className="subtask-log">{st.log}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </main>
    </div>
  );
};

export default App;
