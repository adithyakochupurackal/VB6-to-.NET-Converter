import { useState, useRef } from 'react';

console.log('Loading src/hooks/useConverter.js'); // Debug file loading

export function useConverter() {
  console.log('useConverter hook initialized'); // Debug export
  const [activeTab, setActiveTab] = useState('upload');
  const [file, setFile] = useState(null);
  const [githubUrl, setGithubUrl] = useState('');
  const [isConverting, setIsConverting] = useState(false);
  const [conversionId, setConversionId] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [progress, setProgress] = useState(0);
  const [currentAgent, setCurrentAgent] = useState('');
  const [stageDescription, setStageDescription] = useState('');
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);
  const [duration, setDuration] = useState(null);

  const eventSourceRef = useRef(null);

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const checkHealth = async () => {
    try {
      const response = await fetch(`${apiUrl}/health`);
      const text = await response.text();
      console.log('Health check response:', { status: response.status, statusText: response.statusText, body: text });
      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status} ${response.statusText}`);
      }
      const health = JSON.parse(text);
      setHealthStatus(health);
    } catch (err) {
      console.error('Health check error:', err);
      setHealthStatus({ status: 'unhealthy', error: err.message || 'Failed to connect to API' });
    }
  };

  const startConversion = async () => {
    if (!file && !githubUrl) {
      setError('Please select a file or enter a GitHub URL');
      return;
    }

    setIsConverting(true);
    setError(null);
    setLogs([]);
    setProgress(0);
    setCurrentAgent('');
    setStageDescription('');
    setConversionId(null);
    setDownloadUrl(null);
    setDuration(null);

    try {
      console.log('Attempting to connect to SSE:', `${apiUrl}/stream`);
      eventSourceRef.current = new EventSource(`${apiUrl}/stream`);
      eventSourceRef.current.onopen = () => {
        console.log('SSE connection opened');
      };
      eventSourceRef.current.addEventListener('state_update', (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('SSE state_update:', data);
          setProgress(data.progress || 0);
          setCurrentAgent(data.current_agent || '');
          setStageDescription(data.details?.stage_description || '');
          setLogs((prev) => {
            console.log('Adding state_update to logs:', data);
            return [...prev, { ...data, event_type: 'state_update' }];
          });
        } catch (e) {
          console.error('SSE state_update parsing error:', e);
          setError('Failed to parse state_update data');
        }
      });
      eventSourceRef.current.addEventListener('log', (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('SSE log:', data);
          setLogs((prev) => {
            console.log('Adding log to logs:', data);
            return [...prev, { ...data, event_type: 'log' }];
          });
        } catch (e) {
          console.error('SSE log parsing error:', e);
          setError('Failed to parse log data');
        }
      });
      eventSourceRef.current.addEventListener('error', (event) => {
        console.error('SSE error event:', { event, message: event.message || 'Unknown error', data: event.data });
        setError('Streaming connection failed');
        // Keep connection open unless pipeline is complete
        if (logs.some((log) => log.message === 'Conversion pipeline completed')) {
          eventSourceRef.current?.close();
          console.log('SSE connection closed due to error after pipeline completion');
        } else {
          console.log('Keeping SSE connection open despite error');
        }
      });

      const formData = new FormData();
      if (file) {
        formData.append('zip_file', file);
      } else if (githubUrl) {
        formData.append('github_link', githubUrl);
      }

      const response = await fetch(`${apiUrl}/convert`, {
        method: 'POST',
        body: formData,
      });

      const text = await response.text();
      console.log('Convert response:', { status: response.status, statusText: response.statusText, body: text });

      if (!response.ok) {
        let errorMessage = `Request failed: ${response.status} ${response.statusText}`;
        try {
          const contentType = response.headers.get('content-type');
          if (contentType && contentType.includes('application/json')) {
            const errorData = JSON.parse(text);
            errorMessage = errorData.detail || errorMessage;
          } else {
            errorMessage = text || errorMessage;
          }
        } catch (e) {
          console.error('Error parsing response:', e);
        }
        throw new Error(errorMessage);
      }

      const result = JSON.parse(text);
      setConversionId(result.conversion_id);
      setDownloadUrl(result.download_url);
      setDuration(result.duration);
    } catch (err) {
      console.error('Conversion error:', err);
      setError(err.message || 'An error occurred during conversion');
    } finally {
      setIsConverting(false);
      if (eventSourceRef.current && logs.some((log) => log.message === 'Conversion pipeline completed')) {
        eventSourceRef.current.close();
        console.log('SSE connection closed after pipeline completion');
      } else {
        console.log('Keeping SSE connection open for more events');
      }
    }
  };

  const downloadResult = async () => {
    if (!conversionId) return;

    try {
      const response = await fetch(`${apiUrl}/download/${conversionId}`);
      const text = await response.text();
      console.log('Download response:', { status: response.status, statusText: response.statusText, body: text });
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status} ${response.statusText}`);
      }

      const blob = new Blob([text], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'MyWindowsService.zip';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Download error:', err);
      setError('Failed to download converted project');
    }
  };

  const resetForm = () => {
    setFile(null);
    setGithubUrl('');
    setIsConverting(false);
    setConversionId(null);
    setDownloadUrl(null);
    setProgress(0);
    setCurrentAgent('');
    setStageDescription('');
    setLogs([]);
    setError(null);
    setDuration(null);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      console.log('SSE connection closed on reset');
    }
  };

  return {
    activeTab,
    setActiveTab,
    file,
    setFile,
    githubUrl,
    setGithubUrl,
    isConverting,
    conversionId,
    downloadUrl,
    progress,
    currentAgent,
    stageDescription,
    logs,
    error,
    setError,
    healthStatus,
    duration,
    checkHealth,
    startConversion,
    downloadResult,
    resetForm,
  };
}
