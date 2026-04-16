import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { UploadCloud, Sun, Moon, FileText, ChevronDown, Download, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
  const [error, setError] = useState('');

  const fileInputRef = useRef(null);
  
  useEffect(() => {
    document.documentElement.className = theme;
  }, [theme]);

  const toggleTheme = () => {
    setTheme(t => t === 'dark' ? 'light' : 'dark');
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = async (selectedFile) => {
    if (selectedFile.type !== 'application/pdf') {
      setError('Please upload a PDF file.');
      return;
    }
    setError('');
    setFile(selectedFile);
    
    // Upload File
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    try {
      setUploading(true);
      const res = await axios.post('http://localhost:8000/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data'}
      });
      setFileName(res.data.filename);
      setUploading(false);
      
      // Fetch Funds
      setFetchingFunds(true);
      const fundsRes = await axios.post('http://localhost:8000/extract-funds', { filename: res.data.filename });
      setFunds(fundsRes.data.funds);
      if (fundsRes.data.funds.length > 0) {
        setSelectedFund(fundsRes.data.funds[0]);
      }
      setFetchingFunds(false);
    } catch (err) {
      setUploading(false);
      setFetchingFunds(false);
      setError(err.response?.data?.detail || 'An error occurred during file processing.');
    }
  };

  const handleClear = () => {
    setFile(null);
    setFileName('');
    setFunds([]);
    setSelectedFund('');
    setResult(null);
    setError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleGenerate = async () => {
    if (!selectedFund || !fileName) return;
    try {
      setProcessing(true);
      setError('');
      setResult(null);
      const res = await axios.post('http://localhost:8000/process-fund', {
        filename: fileName,
        fund_name: selectedFund
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred while processing the fund.');
    } finally {
      setProcessing(false);
    }
  };

  const handleDownload = () => {
    if (!result?.word_filename) return;
    window.open(`http://localhost:8000/download/${result.word_filename}`, '_blank');
  };

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-300">
      {/* Header */}
      <header className="border-b border-border bg-card shadow-sm sticky top-0 z-10">
        <div className="container mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <FileText className="text-primary-foreground w-5 h-5" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">FundFactAssist</h1>
          </div>
          <button 
            onClick={toggleTheme}
            className="p-2 rounded-full hover:bg-secondary text-secondary-foreground transition-colors"
            aria-label="Toggle Theme"
          >
            {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </div>
      </header>

      <main className="container mx-auto px-6 py-12 max-w-4xl space-y-8">
        
        {/* Upload Section */}
        <section className="bg-card border border-border rounded-xl p-8 shadow-sm">
          <h2 className="text-xl font-semibold mb-4">Upload Document</h2>
          <div 
            className="border-2 border-dashed border-border rounded-xl p-12 flex flex-col items-center justify-center bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer"
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input 
              type="file" 
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="application/pdf"
              className="hidden"
            />
            {uploading ? (
              <div className="flex flex-col items-center text-muted-foreground">
                <Loader2 className="w-10 h-10 animate-spin mb-4 text-primary" />
                <p>Uploading document...</p>
              </div>
            ) : file ? (
              <div className="flex flex-col items-center text-primary">
                <FileText className="w-12 h-12 mb-4" />
                <p className="font-medium text-lg mb-4">{file.name}</p>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClear();
                  }}
                  className="px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors text-sm font-medium border border-border shadow-sm"
                >
                  Clear / Upload New
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center text-muted-foreground">
                <UploadCloud className="w-12 h-12 mb-4 text-muted-foreground/60" />
                <p className="text-lg font-medium mb-1">Click to choose a file or drag and drop</p>
                <p className="text-sm">Only PDF files are supported</p>
              </div>
            )}
          </div>
          {error && <p className="text-destructive mt-4 text-sm font-medium">{error}</p>}
        </section>

        {/* Selection Section */}
        {fetchingFunds ? (
          <div className="flex items-center justify-center p-8 bg-card border border-border rounded-xl shadow-sm">
            <Loader2 className="w-6 h-6 animate-spin mr-3 text-primary" />
            <span>Scanning document for funds...</span>
          </div>
        ) : funds.length > 0 && (
          <section className="bg-card border border-border rounded-xl p-6 shadow-sm flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-muted-foreground mb-2">Select Fund</label>
              <div className="relative">
                <select 
                  className="w-full appearance-none bg-background border border-border text-foreground py-3 pl-4 pr-10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-shadow"
                  value={selectedFund}
                  onChange={(e) => setSelectedFund(e.target.value)}
                >
                  {funds.map((fund, idx) => (
                    <option key={idx} value={fund}>{fund}</option>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground pointer-events-none" />
              </div>
            </div>
            <button 
              onClick={handleGenerate}
              disabled={processing || !selectedFund}
              className="w-full sm:w-auto px-8 py-3 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-md shadow-primary/20"
            >
              {processing ? (
                <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Processing...</>
              ) : (
                'Generate Report'
              )}
            </button>
          </section>
        )}

        {/* Result Section */}
        {result && (
          <section className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col flex-1 animate-in slide-in-from-bottom-4 fade-in duration-500">
            <div className="flex items-center justify-between border-b border-border px-6 py-4 bg-secondary/30">
              <h2 className="text-lg font-semibold">Extracted Content</h2>
              {result.word_filename && (
                <button 
                  onClick={handleDownload}
                  className="flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground font-medium rounded-md hover:bg-accent/80 transition-colors border border-border shadow-sm text-sm"
                >
                  <Download className="w-4 h-4" />
                  Download Word Document
                </button>
              )}
            </div>
            <div className="p-6 bg-background">
              <div className="prose prose-sm dark:prose-invert max-w-none text-foreground prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-a:text-primary mb-8 border-b border-border pb-8">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result.markdown_content}
                </ReactMarkdown>
              </div>
              
              {/* Reference Section */}
              {result.used_pages && result.used_pages.length > 0 && (
                <div className="bg-muted/30 p-4 rounded-lg border border-border">
                  <h3 className="text-sm font-semibold text-foreground flex items-center gap-2 mb-2">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    Extraction Reference
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Data was extracted from PDF page(s): <span className="font-medium text-foreground">{result.used_pages.join(', ')}</span>
                  </p>
                </div>
              )}
            </div>
          </section>
        )}

      </main>
    </div>
  );
}
