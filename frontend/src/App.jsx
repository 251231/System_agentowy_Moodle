import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, Languages, Settings as SettingsIcon, FileCheck, Loader2, Download, AlertCircle } from 'lucide-react';
import './App.css';

const App = () => {
    const [file, setFile] = useState(null);
    const [status, setStatus] = useState('idle'); // idle, uploading, processing, completed, error
    const [taskId, setTaskId] = useState(null);
    const [progress, setProgress] = useState(0);
    const [config, setConfig] = useState({
        sourceLang: 'en',
        targetLangs: 'en,pl',
        apiType: 'none',
        apiKey: '',
    });

    const handleFileChange = (e) => {
        if (e.target.files[0]) {
            setFile(e.target.files[0]);
            setStatus('idle');
        }
    };

    const startTranslation = async () => {
        if (!file) return;

        setStatus('uploading');
        const formData = new FormData();
        formData.append('file', file);
        formData.append('source_lang', config.sourceLang);
        formData.append('target_langs', config.targetLangs);
        formData.append('api_type', config.apiType);
        if (config.apiKey) formData.append('api_key', config.apiKey);

        try {
            const res = await axios.post('/api/translate', formData);
            setTaskId(res.data.task_id);
            setStatus('processing');
        } catch (err) {
            console.error(err);
            setStatus('error');
        }
    };

    useEffect(() => {
        let interval;
        if (status === 'processing' && taskId) {
            interval = setInterval(async () => {
                try {
                    const res = await axios.get(`/api/status/${taskId}`);
                    if (res.data.status === 'completed') {
                        setStatus('completed');
                        clearInterval(interval);
                    } else if (res.data.status === 'failed') {
                        setStatus('error');
                        clearInterval(interval);
                    }
                } catch (err) {
                    console.error(err);
                }
            }, 2000);
        }
        return () => clearInterval(interval);
    }, [status, taskId]);

    const downloadResult = () => {
        window.open(`/api/download/${taskId}`, '_blank');
    };

    return (
        <div className="app-container">
            <div className="background-shapes">
                <div className="shape shape-1"></div>
                <div className="shape shape-2"></div>
            </div>

            <main className="content">
                <motion.header 
                    initial={{ y: -50, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ duration: 0.8 }}
                >
                    <h1>Moodle MBZ Translator</h1>
                    <p>Upgrade your courses with automatic {`{mlang}`} tags.</p>
                </motion.header>

                <div className="glass-grid">
                    <section className="config-panel">
                        <div className="panel-header">
                            <SettingsIcon size={20} />
                            <h2>Configuration</h2>
                        </div>
                        
                        <div className="input-group">
                            <label>Source Language</label>
                            <input 
                                type="text" 
                                value={config.sourceLang} 
                                onChange={(e) => setConfig({...config, sourceLang: e.target.value})}
                                placeholder="e.g. en"
                            />
                        </div>

                        <div className="input-group">
                            <label>Target Languages (comma separated)</label>
                            <input 
                                type="text" 
                                value={config.targetLangs} 
                                onChange={(e) => setConfig({...config, targetLangs: e.target.value})}
                                placeholder="e.g. en,pl,de"
                            />
                        </div>

                        <div className="input-group">
                            <label>Translation Engine</label>
                            <select 
                                value={config.apiType}
                                onChange={(e) => setConfig({...config, apiType: e.target.value})}
                            >
                                <option value="none">Mock (Prefix [PL])</option>
                                <option value="openai">OpenAI (GPT-4o)</option>
                                <option value="deepl">DeepL</option>
                            </select>
                        </div>

                        {config.apiType !== 'none' && (
                            <div className="input-group">
                                <label>API Key</label>
                                <input 
                                    type="password" 
                                    value={config.apiKey}
                                    onChange={(e) => setConfig({...config, apiKey: e.target.value})}
                                    placeholder="Enter your key..."
                                />
                            </div>
                        )}
                    </section>

                    <section className="upload-panel">
                        <div className="panel-header">
                            <Upload size={20} />
                            <h2>MBZ File</h2>
                        </div>

                        <div className={`dropzone ${file ? 'has-file' : ''}`}>
                            <input type="file" onChange={handleFileChange} id="fileInput" accept=".mbz" />
                            <label htmlFor="fileInput">
                                <div className="icon-wrapper">
                                    <FileCheck size={40} />
                                </div>
                                <span>{file ? file.name : "Drag & Drop .mbz or Click to Browse"}</span>
                            </label>
                        </div>

                        <div className="action-area">
                            <AnimatePresence mode="wait">
                                {status === 'idle' && (
                                    <motion.button 
                                        key="btn-start"
                                        whileHover={{ scale: 1.05 }}
                                        whileTap={{ scale: 0.95 }}
                                        onClick={startTranslation}
                                        disabled={!file}
                                        className="btn-primary"
                                    >
                                        Start Translation
                                    </motion.button>
                                )}

                                {(status === 'uploading' || status === 'processing') && (
                                    <motion.div key="status-loading" className="status-loader">
                                        <Loader2 className="spin" size={24} />
                                        <span>{status === 'uploading' ? 'Uploading...' : 'Processing XMLs...'}</span>
                                    </motion.div>
                                )}

                                {status === 'completed' && (
                                    <motion.button 
                                        key="btn-download"
                                        initial={{ scale: 0.8, opacity: 0 }}
                                        animate={{ scale: 1, opacity: 1 }}
                                        onClick={downloadResult}
                                        className="btn-success"
                                    >
                                        <Download size={20} /> Download MBZ
                                    </motion.button>
                                )}

                                {status === 'error' && (
                                    <div key="status-error" className="status-error">
                                        <AlertCircle size={20} />
                                        <span>Processing Failed</span>
                                    </div>
                                )}
                            </AnimatePresence>
                        </div>
                    </section>
                </div>
            </main>
        </div>
    );
};

export default App;
