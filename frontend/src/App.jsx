import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import {
  UploadCloud, Sun, Moon, FileText, ChevronDown, Download,
  Copy, Check, Loader2, Sparkles, RefreshCw, AlertCircle, X, Search,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatBytes(bytes) {
  if (!bytes) return '';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// ── Toast System ─────────────────────────────────────────────────────────────

function Toast({ toasts, removeToast }) {
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl shadow-xl border max-w-sm bg-destructive text-destructive-foreground border-destructive/50 animate-in slide-in-from-right-4 fade-in duration-300"
        >
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 opacity-90" />
          <p className="text-sm flex-1 leading-snug">{toast.message}</p>
          <button
            onClick={() => removeToast(toast.id)}
            className="opacity-70 hover:opacity-100 transition-opacity flex-shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}

// ── Step Indicator ───────────────────────────────────────────────────────────

function StepIndicator({ getStatus }) {
  const steps = [
    { n: 1, label: 'Upload PDF' },
    { n: 2, label: 'Select Fund' },
    { n: 3, label: 'Generate Report' },
  ];

  return (
    <div className="flex items-start justify-center gap-0 select-none mb-2">
      {steps.map((step, idx) => {
        const status = getStatus(step.n);
        const isComplete = status === 'complete';
        const isActive = status === 'active';

        return (
          <div key={step.n} className="flex items-start">
            <div className="flex flex-col items-center w-28">
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-500 ${
                  isComplete
                    ? 'text-white shadow-md shadow-primary/30'
                    : isActive
                    ? 'border-2 border-primary text-primary ring-4 ring-primary/15'
                    : 'bg-muted text-muted-foreground'
                }`}
                style={isComplete ? { background: 'var(--brand-gradient)' } : {}}
              >
                {isComplete ? <Check className="w-4 h-4" /> : step.n}
              </div>
              <span
                className={`mt-2 text-xs font-medium text-center leading-tight ${
                  isComplete || isActive ? 'text-foreground' : 'text-muted-foreground'
                }`}
              >
                {step.label}
              </span>
            </div>

            {idx < steps.length - 1 && (
              <div className="flex-1 mt-[1.1rem] w-12">
                <div
                  className={`h-0.5 transition-all duration-700 ${
                    getStatus(step.n + 1) !== 'idle' || isComplete
                      ? 'opacity-100'
                      : 'bg-border'
                  }`}
                  style={
                    getStatus(step.n + 1) !== 'idle' || isComplete
                      ? { background: 'var(--brand-gradient)' }
                      : {}
                  }
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Skeleton Loader ───────────────────────────────────────────────────────────

function ResultSkeleton() {
  return (
    <section className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden animate-in fade-in duration-300">
      <div className="px-6 py-4 border-b border-border bg-secondary/20 flex items-center gap-3">
        <Loader2 className="w-5 h-5 animate-spin text-primary flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold">Extracting fund data with AI…</p>
          <p className="text-xs text-muted-foreground">This may take a few seconds</p>
        </div>
      </div>
      <div className="p-6 space-y-3">
        {[75, 55, 88, 42, 68, 80, 50].map((w, i) => (
          <div
            key={i}
            className="h-3 bg-muted rounded-full skeleton"
            style={{ width: `${w}%`, animationDelay: `${i * 120}ms` }}
          />
        ))}
      </div>
    </section>
  );
}

// ── Custom Fund Dropdown ──────────────────────────────────────────────────────

function FundDropdown({ funds, selectedFund, onChange }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef(null);
  const searchRef = useRef(null);
  const listRef = useRef(null);

  const filtered = funds.filter((f) =>
    f.toLowerCase().includes(search.toLowerCase())
  );

  // Close on outside click
  useEffect(() => {
    function handleClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
        setSearch('');
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Focus search on open
  useEffect(() => {
    if (open && searchRef.current) {
      setTimeout(() => searchRef.current?.focus(), 50);
    }
  }, [open]);

  // Scroll selected item into view
  useEffect(() => {
    if (open && listRef.current) {
      const selectedEl = listRef.current.querySelector('[data-selected="true"]');
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [open]);

  const handleSelect = (fund) => {
    onChange(fund);
    setOpen(false);
    setSearch('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setOpen(false);
      setSearch('');
    }
  };

  // Highlight matching text
  const highlight = (text, query) => {
    if (!query) return text;
    const idx = text.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return text;
    return (
      <>
        {text.slice(0, idx)}
        <mark className="bg-primary/20 text-foreground rounded-sm px-0.5">
          {text.slice(idx, idx + query.length)}
        </mark>
        {text.slice(idx + query.length)}
      </>
    );
  };

  return (
    <div ref={containerRef} className="relative w-full" onKeyDown={handleKeyDown}>
      {/* Trigger */}
      <button
        type="button"
        id="fund-select"
        onClick={() => setOpen((v) => !v)}
        className={`w-full flex items-center justify-between gap-3 px-4 py-3 rounded-xl border text-sm font-medium transition-all duration-200 bg-background text-left ${
          open
            ? 'border-primary ring-2 ring-primary/20'
            : 'border-border hover:border-primary/50 hover:bg-secondary/20'
        }`}
      >
        <span className="truncate text-foreground">{selectedFund || 'Select a fund…'}</span>
        <ChevronDown
          className={`w-4 h-4 text-muted-foreground flex-shrink-0 transition-transform duration-200 ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute z-30 mt-2 w-full bg-card border border-border rounded-2xl shadow-2xl shadow-black/20 overflow-hidden animate-in slide-in-from-top-2 fade-in duration-150">
          {/* Search bar */}
          <div className="px-3 pt-3 pb-2 border-b border-border/60">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary/40 border border-border/50 focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/10 transition-all">
              <Search className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
              <input
                ref={searchRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search funds…"
                className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none border-none"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Count label */}
          <div className="px-4 py-1.5 flex items-center justify-between">
            <span className="text-[11px] font-medium text-muted-foreground">
              {filtered.length === funds.length
                ? `${funds.length} funds`
                : `${filtered.length} of ${funds.length} funds`}
            </span>
          </div>

          {/* List */}
          <ul
            ref={listRef}
            className="max-h-64 overflow-y-auto px-2 pb-2 space-y-0.5"
            role="listbox"
          >
            {filtered.length === 0 ? (
              <li className="px-3 py-8 text-center text-sm text-muted-foreground">
                No funds match "{search}"
              </li>
            ) : (
              filtered.map((fund, idx) => {
                const isSelected = fund === selectedFund;
                return (
                  <li
                    key={idx}
                    role="option"
                    aria-selected={isSelected}
                    data-selected={isSelected}
                    onClick={() => handleSelect(fund)}
                    className={`flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg text-sm cursor-pointer transition-all duration-100 ${
                      isSelected
                        ? 'font-medium text-primary'
                        : 'text-foreground hover:bg-secondary/60'
                    }`}
                    style={isSelected ? { background: 'color-mix(in sRGB, var(--primary) 10%, transparent)' } : {}}
                  >
                    <span className="leading-snug">{highlight(fund, search)}</span>
                    {isSelected && (
                      <Check className="w-3.5 h-3.5 flex-shrink-0 text-primary" />
                    )}
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [theme, setTheme] = useState('dark');
  const [file, setFile] = useState(null);
  const [fileName, setFileName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [fetchingFunds, setFetchingFunds] = useState(false);
  const [funds, setFunds] = useState([]);
  const [selectedFund, setSelectedFund] = useState('');
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [toasts, setToasts] = useState([]);

  const fileInputRef = useRef(null);
  const resultRef = useRef(null);

  useEffect(() => {
    document.documentElement.className = theme;
  }, [theme]);

  useEffect(() => {
    if (result && resultRef.current) {
      setTimeout(() => {
        resultRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 150);
    }
  }, [result]);

  const addToast = (message) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message }]);
    setTimeout(() => removeToast(id), 5000);
  };

  const removeToast = (id) =>
    setToasts((prev) => prev.filter((t) => t.id !== id));

  const getStatus = (step) => {
    if (step === 1) {
      if (funds.length > 0 || result) return 'complete';
      if (file || uploading || fetchingFunds) return 'active';
      return 'idle';
    }
    if (step === 2) {
      if (result) return 'complete';
      if (funds.length > 0) return 'active';
      return 'idle';
    }
    if (step === 3) {
      if (result) return 'complete';
      if (processing) return 'active';
      return 'idle';
    }
  };

  const handleDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const handleDragLeave = () => setDragOver(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.[0]) handleFileSelected(e.dataTransfer.files[0]);
  };

  const handleFileChange = (e) => {
    if (e.target.files?.[0]) handleFileSelected(e.target.files[0]);
  };

  const handleFileSelected = async (selectedFile) => {
    if (selectedFile.type !== 'application/pdf') {
      addToast('Please upload a PDF file. Other formats are not supported.');
      return;
    }

    setFile(selectedFile);
    setFunds([]);
    setSelectedFund('');
    setResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      setUploading(true);
      const res = await axios.post('http://localhost:8000/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setFileName(res.data.filename);
      setUploading(false);

      setFetchingFunds(true);
      const fundsRes = await axios.post('http://localhost:8000/extract-funds', {
        filename: res.data.filename,
      });
      setFunds(fundsRes.data.funds);
      if (fundsRes.data.funds.length > 0) setSelectedFund(fundsRes.data.funds[0]);
      setFetchingFunds(false);
    } catch (err) {
      setUploading(false);
      setFetchingFunds(false);
      addToast(err.response?.data?.detail || 'An error occurred during file processing.');
    }
  };

  const handleClear = () => {
    setFile(null);
    setFileName('');
    setFunds([]);
    setSelectedFund('');
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleGenerate = async () => {
    if (!selectedFund || !fileName) return;
    try {
      setProcessing(true);
      setResult(null);
      const res = await axios.post('http://localhost:8000/process-fund', {
        filename: fileName,
        fund_name: selectedFund,
      });
      setResult(res.data);
    } catch (err) {
      addToast(err.response?.data?.detail || 'An error occurred while processing the fund.');
    } finally {
      setProcessing(false);
    }
  };

  const handleGenerateAnother = () => setResult(null);

  const handleCopy = async () => {
    if (!result?.markdown_content) return;
    try {
      await navigator.clipboard.writeText(result.markdown_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      addToast('Failed to copy content to clipboard.');
    }
  };

  const handleDownload = async () => {
    if (!result?.markdown_content) return;
    try {
      setDownloading(true);
      const response = await axios.post(
        'http://localhost:8000/download-word',
        { markdown_content: result.markdown_content, fund_name: selectedFund },
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute(
        'download',
        `${selectedFund.replace(/[^a-zA-Z0-9]/g, '_')}_Factsheet.docx`
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      addToast('Failed to generate Word document. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-300 flex flex-col">
      <Toast toasts={toasts} removeToast={removeToast} />

      {/* ── Header ─────────────────────────────────────────── */}
      <header className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="w-full px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center shadow-md shadow-primary/20"
              style={{ background: 'var(--brand-gradient)' }}
            >
              <FileText className="text-white w-4 h-4" />
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight leading-none">
                FundFactAssist
              </h1>
              <p className="text-[11px] text-muted-foreground leading-none mt-0.5">
                AI-Powered Factsheet Extraction
              </p>
            </div>
          </div>
          <button
            id="theme-toggle"
            onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
            className="p-2 rounded-full hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Toggle Theme"
          >
            {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </div>
      </header>

      {/* ── Main Content ───────────────────────────────────── */}
      <main className="container mx-auto px-6 py-10 max-w-5xl space-y-6 flex-1">

        <StepIndicator getStatus={getStatus} />

        {/* ── Upload Section ──────────────────────────────── */}
        <section className="bg-card border border-border rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
              style={{ background: 'var(--brand-gradient)' }}
            >
              1
            </div>
            <h2 className="text-sm font-semibold">Upload Factsheet PDF</h2>
          </div>

          <div
            id="upload-dropzone"
            className={`border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center text-center transition-all duration-200 cursor-pointer ${
              dragOver
                ? 'border-primary bg-primary/8 scale-[1.01] shadow-inner'
                : file
                ? 'border-primary/40 bg-primary/4'
                : 'border-border hover:border-primary/50 hover:bg-secondary/30 bg-secondary/10'
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="application/pdf"
              className="hidden"
              id="file-input"
            />

            {uploading ? (
              <div className="flex flex-col items-center">
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                  <Loader2 className="w-7 h-7 animate-spin text-primary" />
                </div>
                <p className="font-semibold text-foreground">Uploading document…</p>
                <p className="text-sm text-muted-foreground mt-1">Please wait</p>
              </div>
            ) : fetchingFunds ? (
              <div className="flex flex-col items-center">
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                  <Loader2 className="w-7 h-7 animate-spin text-primary" />
                </div>
                <p className="font-semibold text-foreground">Scanning for funds…</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Identifying mutual funds in document
                </p>
              </div>
            ) : file ? (
              <div className="flex flex-col items-center">
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                  <FileText className="w-7 h-7 text-primary" />
                </div>
                <p className="font-semibold text-foreground text-base mb-0.5 break-all px-4">
                  {file.name}
                </p>
                <p className="text-sm text-muted-foreground mb-4">
                  {formatBytes(file.size)} · PDF Document
                </p>

                {funds.length > 0 && (
                  <div className="mb-4 flex items-center gap-1.5 px-3 py-1.5 bg-green-500/10 text-green-600 dark:text-green-400 rounded-full text-xs font-semibold border border-green-500/20">
                    <Check className="w-3.5 h-3.5" />
                    {funds.length} fund{funds.length !== 1 ? 's' : ''} detected
                  </div>
                )}

                <button
                  id="clear-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClear();
                  }}
                  className="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/70 transition-colors text-sm font-medium border border-border"
                >
                  Clear / Upload New
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="w-14 h-14 rounded-2xl bg-secondary flex items-center justify-center mb-4">
                  <UploadCloud className="w-7 h-7 text-muted-foreground" />
                </div>
                <p className="text-base font-semibold text-foreground mb-1">
                  Drop your PDF here
                </p>
                <p className="text-sm text-muted-foreground mb-4">
                  or click to browse files
                </p>
                <span className="text-xs bg-secondary text-muted-foreground px-3 py-1 rounded-full font-medium">
                  PDF files only
                </span>
              </div>
            )}
          </div>
        </section>

        {/* ── Fund Selection ──────────────────────────────── */}
        {funds.length > 0 && !result && (
          <section className="bg-card border border-border rounded-2xl p-6 shadow-sm animate-in slide-in-from-bottom-4 fade-in duration-400">
            <div className="flex items-center gap-2 mb-4">
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                style={{ background: 'var(--brand-gradient)' }}
              >
                2
              </div>
              <h2 className="text-sm font-semibold">Select Fund to Extract</h2>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 items-end">
              <div className="flex-1 w-full">
                <label
                  htmlFor="fund-select"
                  className="block text-xs font-medium text-muted-foreground mb-2"
                >
                  {funds.length} fund{funds.length !== 1 ? 's' : ''} found in this document
                </label>
                <FundDropdown
                  funds={funds}
                  selectedFund={selectedFund}
                  onChange={setSelectedFund}
                />
              </div>

              <button
                id="generate-btn"
                onClick={handleGenerate}
                disabled={processing || !selectedFund}
                className="w-full sm:w-auto px-7 py-3 text-white font-semibold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm hover:opacity-90 hover:shadow-lg hover:shadow-primary/30 active:scale-[0.98]"
                style={{ background: 'var(--brand-gradient)' }}
              >
                {processing ? (
                  <><Loader2 className="w-4 h-4 animate-spin" />Processing…</>
                ) : (
                  <><Sparkles className="w-4 h-4" />Generate Report</>
                )}
              </button>
            </div>
          </section>
        )}

        {/* ── Skeleton while processing ───────────────────── */}
        {processing && <ResultSkeleton />}

        {/* ── Result Section ──────────────────────────────── */}
        {result && (
          <section
            ref={resultRef}
            className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-500"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border px-6 py-4 bg-secondary/10">
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center shadow-sm shrink-0"
                  style={{ background: 'var(--brand-gradient)' }}
                >
                  <Check className="w-4 h-4 text-white" />
                </div>
                <div>
                  <p className="text-sm font-semibold leading-tight">Extracted Content</p>
                  <p className="text-xs text-muted-foreground leading-tight mt-0.5 truncate max-w-xs">
                    {selectedFund}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <button
                  id="generate-another-btn"
                  onClick={handleGenerateAnother}
                  className="flex items-center gap-1.5 px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-colors text-xs font-medium border border-border"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Generate Another</span>
                </button>

                <button
                  id="copy-btn"
                  onClick={handleCopy}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg transition-all text-xs font-semibold border ${
                    copied
                      ? 'bg-green-500/10 text-green-500 border-green-500/30'
                      : 'bg-primary/8 text-primary border-primary/20 hover:bg-primary/15'
                  }`}
                >
                  {copied ? (
                    <><Check className="w-3.5 h-3.5" />Copied!</>
                  ) : (
                    <><Copy className="w-3.5 h-3.5" />Copy</>
                  )}
                </button>

                <button
                  id="download-word-btn"
                  onClick={handleDownload}
                  disabled={downloading}
                  className="flex items-center gap-1.5 px-4 py-2 text-white font-semibold rounded-lg transition-all text-xs disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 active:scale-[0.97]"
                  style={{ background: 'var(--brand-gradient)' }}
                >
                  {downloading ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin" />Generating…</>
                  ) : (
                    <><Download className="w-3.5 h-3.5" />Download Word</>
                  )}
                </button>
              </div>
            </div>

            <div className="p-6 md:p-8 bg-background">
              <div
                id="extracted-content"
                className="prose prose-sm md:prose-base dark:prose-invert max-w-none
                  text-foreground
                  prose-headings:text-foreground prose-headings:font-semibold
                  prose-p:text-foreground prose-p:leading-relaxed
                  prose-strong:text-foreground
                  prose-a:text-primary prose-a:no-underline hover:prose-a:underline
                  prose-li:text-foreground
                  prose-hr:border-border
                  mb-6 pb-6 border-b border-border"
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result.markdown_content}
                </ReactMarkdown>
              </div>

              {result.used_pages?.length > 0 && (
                <div
                  className="flex items-start gap-3 p-4 rounded-xl border"
                  style={{ background: 'var(--brand-gradient-subtle)', borderColor: 'color-mix(in sRGB, var(--primary) 20%, transparent)' }}
                >
                  <FileText className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-foreground mb-0.5">
                      Extraction Reference
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Data extracted from PDF page
                      {result.used_pages.length > 1 ? 's' : ''}:{' '}
                      <span className="font-semibold text-foreground">
                        {result.used_pages.join(', ')}
                      </span>
                    </p>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}
      </main>

      {/* ── Footer ─────────────────────────────────────────── */}
      <footer className="border-t border-border py-5 mt-8">
        <p className="text-center text-xs text-muted-foreground">
          FundFactAssist · AI-Powered Mutual Fund Factsheet Extraction
        </p>
      </footer>
    </div>
  );
}