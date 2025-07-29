import { useState, useRef } from 'react';
import { Box, Card, Typography, Tabs, Tab, Input, Button, Alert } from '@mui/material';
import { Upload, Github, Download, CheckCircle, Zap, Loader2 } from 'lucide-react';
import { Transition } from '@headlessui/react';
import { useConverter } from '../../hooks/useConverter'; 

export function ConverterForm() {
  const {
    activeTab,
    setActiveTab,
    file,
    setFile,
    githubUrl,
    setGithubUrl,
    isConverting,
    conversionId,
    downloadUrl,
    duration,
    error,
    setError,
    startConversion,
    resetForm,
    downloadResult,
  } = useConverter();
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.size > 50 * 1024 * 1024) {
        setError('File size must be less than 50MB');
        return;
      }
      if (!selectedFile.name.endsWith('.zip')) {
        setError('Please select a ZIP file');
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  };

  return (
    <Card>
      <Box sx={{ p: 3 }}>
        <Typography variant="h4">Convert VB6 Project</Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
          Upload a ZIP file containing your VB6 project or provide a GitHub repository URL.
        </Typography>
      </Box>
      <Box sx={{ px: 3, pb: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(_, value) => setActiveTab(value)}
          variant="fullWidth"
          sx={{ bgcolor: 'grey.100', borderRadius: 1 }}
        >
          <Tab label="Upload ZIP" value="upload" icon={<Upload className="h-4 w-4" />} iconPosition="start" />
          <Tab label="GitHub URL" value="github" icon={<Github className="h-4 w-4" />} iconPosition="start" />
        </Tabs>

        <Transition
          show={activeTab === 'upload'}
          enter="transition ease-out duration-200"
          enterFrom="opacity-0 translate-y-1"
          enterTo="opacity-100 translate-y-0"
        >
          <Box sx={{ display: activeTab === 'upload' ? 'block' : 'none' }}>
            <Typography variant="body2" component="label" htmlFor="file">
              VB6 Project ZIP File (max 50MB)
            </Typography>
            <Input
              id="file"
              type="file"
              inputRef={fileInputRef}
              inputProps={{ accept: '.zip' }}
              onChange={handleFileChange}
              disabled={isConverting}
              sx={{ mt: 1 }}
            />
            {file && (
              <Typography variant="caption" sx={{ mt: 1, color: 'text.secondary' }}>
                Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </Typography>
            )}
          </Box>
        </Transition>

        <Transition
          show={activeTab === 'github'}
          enter="transition ease-out duration-200"
          enterFrom="opacity-0 translate-y-1"
          enterTo="opacity-100 translate-y-0"
        >
          <Box sx={{ display: activeTab === 'github' ? 'block' : 'none' }}>
            <Typography variant="body2" component="label" htmlFor="github">
              GitHub Repository URL
            </Typography>
            <Input
              id="github"
              type="url"
              placeholder="https://github.com/username/repository"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              disabled={isConverting}
              sx={{ mt: 1 }}
            />
          </Box>
        </Transition>

        {error && (
          <Alert color="error">
            <Typography variant="body2">{error}</Typography>
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            onClick={startConversion}
            disabled={isConverting || (!file && !githubUrl)}
            startIcon={isConverting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            sx={{ flex: 1 }}
          >
            {isConverting ? 'Converting...' : 'Start Conversion'}
          </Button>
          {(conversionId || isConverting) && (
            <Button variant="outlined" onClick={resetForm}>
              Reset
            </Button>
          )}
        </Box>

        {downloadUrl && conversionId && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, color: 'success.main' }}>
              <CheckCircle className="h-5 w-5" />
              <Typography variant="body1" sx={{ fontWeight: 'medium' }}>
                Conversion Complete!
              </Typography>
              {duration && <Typography variant="caption">{duration.toFixed(2)}s</Typography>}
            </Box>
            <Button
              variant="contained"
              color="success"
              onClick={downloadResult}
              startIcon={<Download className="h-4 w-4" />}
            >
              Download .NET Project
            </Button>
          </Box>
        )}
      </Box>
    </Card>
  );
}
