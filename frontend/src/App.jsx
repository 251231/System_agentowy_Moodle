import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload, Languages, BrainCircuit, FileCheck, Loader2,
  Download, AlertCircle, CheckCircle2, Clock, ChevronDown, ChevronUp
} from 'lucide-react';
import './App.css';

const API = 'http://localhost:8000';

const App = () => {
  const [file, setFile] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [config, setConfig] = useState({
    translate: true,
    generate_h5p: false,
    source_lang: 'en',
    target_langs: 'en,pl',
    api_type: 'none',
    api_key: '',
  });

  // ── polling listy zadań ──────────────────────────────────────────────────
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

  // ── obsługa pliku ────────────────────────────────────────────────────────
  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]);
  };

  // ── submit ───────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setIsSubmitting(true);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('translate', config.translate);
    fd.append('generate_h5p', config.generate_h5p);
    fd.append('source_lang', config.source_lang);
    fd.append('target_langs', config.target_langs);
    fd.append('api_type', config.api_type);
    if (config.api_key) fd.append('api_key', config.api_key);
    try {
      await axios.post(`${API}/tasks`, fd);
      setFile(null);
      fetchTasks();
    } catch (_) {
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── pomocnicze ───────────────────────────────────────────────────────────
  const toggleExpand = (id) => setExpanded(p => ({ ...p, [id]: !p[id] }));

  const statusIcon = (s) => ({
    completed: <CheckCircle2 size={14} className="icon-green" />,
    processing: <Loader2 size={14} className="icon-blue spin" />,
    failed: <AlertCircle size={14} className="icon-red" />,
  }[s] ?? <Clock size={14} className="icon-muted" />);

  const statusLabel = (s) => ({
    completed: 'Ukończone',
    processing: 'Przetwarzanie',
    failed: 'Błąd',
    pending: 'Oczekuje',
  }[s] ?? s);

  return (
    <div className="app-container">
      <div className="background-shapes">
        <div className="shape shape-1" />
        <div className="shape shape-2" />
      </div>

      <main className="content">
        {/* ── Header ── */}
        <motion.header
          initial={{ y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.7 }}
        >
          <h1>Moodle AI Agent System</h1>
          <p>Tłumaczenie i kogeneracja treści H5P przy użyciu LLM</p>
        </motion.header>

        {/* ── Main grid ── */}
        <div className="glass-grid">

          {/* ── Config Panel ── */}
          <motion.section
            className="config-panel"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <div className="panel-header">
              <BrainCircuit size={18} />
              <h2>Konfiguracja</h2>
            </div>

            <form onSubmit={handleSubmit}>
              {/* Dropzone */}
              <div
                className={`dropzone${file ? ' has-file' : ''}`}
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
              >
                <input type="file" id="fileInput" accept=".mbz"
                  onChange={(e) => setFile(e.target.files[0])} />
                <label htmlFor="fileInput">
                  <div className="icon-wrapper">
                    <FileCheck size={36} />
                  </div>
                  <span>
                    {file ? file.name : 'Przeciągnij plik .mbz lub kliknij'}
                  </span>
                </label>
              </div>

              {/* Agenci */}
              <div className="toggle-group">
                <label className="toggle-row">
                  <input type="checkbox" checked={config.translate}
                    onChange={(e) => setConfig({ ...config, translate: e.target.checked })} />
                  <Languages size={16} className="icon-blue" />
                  <span>Agent Tłumaczący</span>
                </label>

                {config.translate && (
                  <div className="input-group indent">
                    <label>Języki docelowe</label>
                    <input type="text" value={config.target_langs}
                      onChange={(e) => setConfig({ ...config, target_langs: e.target.value })}
                      placeholder="np. en,pl,de" />
                  </div>
                )}

                <label className="toggle-row">
                  <input type="checkbox" checked={config.generate_h5p}
                    onChange={(e) => setConfig({ ...config, generate_h5p: e.target.checked })} />
                  <BrainCircuit size={16} className="icon-purple" />
                  <span>Agent H5P (Fiszki AI)</span>
                </label>
              </div>

              {/* Silnik AI */}
              <div className="input-group">
                <label>Silnik tłumaczenia</label>
                <select value={config.api_type}
                  onChange={(e) => setConfig({ ...config, api_type: e.target.value })}>
                  <option value="none">Mock (bez AI)</option>
                  <option value="openai">OpenAI (GPT-4o)</option>
                  <option value="deepl">DeepL</option>
                </select>
              </div>

              {config.api_type !== 'none' && (
                <div className="input-group">
                  <label>Klucz API</label>
                  <input type="password" value={config.api_key}
                    onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
                    placeholder="sk-..." />
                </div>
              )}

              <button type="submit"
                className="btn-primary"
                disabled={!file || isSubmitting || (!config.translate && !config.generate_h5p)}
              >
                {isSubmitting
                  ? <><Loader2 size={18} className="spin" /> Wysyłanie...</>
                  : <><Upload size={18} /> Uruchom Agenty</>}
              </button>
            </form>
          </motion.section>

          {/* ── Task Feed ── */}
          <motion.section
            className="upload-panel task-feed"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
          >
            <div className="panel-header">
              <Clock size={18} />
              <h2>Monitor Zadań</h2>
              <span className="live-badge">LIVE</span>
            </div>

            <div className="task-list">
              <AnimatePresence>
                {tasks.length === 0 && (
                  <motion.div className="empty-state"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    <FileCheck size={48} className="icon-muted" />
                    <p>Brak zadań. Prześlij pierwszą paczkę MBZ.</p>
                  </motion.div>
                )}

                {tasks.map((task) => (
                  <motion.div
                    key={task.id}
                    className={`task-card status-${task.status}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    layout
                  >
                    <div className="task-header" onClick={() => toggleExpand(task.id)}>
                      <div className="task-info">
                        <span className="task-filename">{task.original_filename}</span>
                        <span className="task-id">#{task.id.split('-')[0]}</span>
                      </div>
                      <div className="task-right">
                        <span className={`status-badge badge-${task.status}`}>
                          {statusIcon(task.status)}
                          {statusLabel(task.status)}
                        </span>
                        {expanded[task.id]
                          ? <ChevronUp size={16} className="icon-muted" />
                          : <ChevronDown size={16} className="icon-muted" />}
                      </div>
                    </div>

                    {/* Subtasks */}
                    <AnimatePresence>
                      {expanded[task.id] && task.subtasks?.length > 0 && (
                        <motion.div className="subtask-list"
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                        >
                          {task.subtasks.map((st, i) => (
                            <div key={i} className="subtask-row">
                              {statusIcon(st.status)}
                              <span className="subtask-name">{st.agent}</span>
                              <span className="subtask-log">{st.log}</span>
                            </div>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Download */}
                    {task.status === 'completed' && (
                      <a className="btn-success btn-download"
                        href={`${API}/download/${task.id}`} target="_blank" rel="noreferrer">
                        <Download size={16} /> Pobierz plik
                      </a>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </motion.section>
        </div>
      </main>
    </div>
  );
};

export default App;
