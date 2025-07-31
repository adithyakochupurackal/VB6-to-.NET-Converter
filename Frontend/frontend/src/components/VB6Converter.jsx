"use client"

import { useState, useEffect, useRef } from "react"
import styled from "styled-components"
import UploadSection from "./UploadSection.jsx"
import ConversionFlow from "./ConversionFlow.jsx"

const MainContent = styled.main`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem 1rem;
`

const HeaderSection = styled.div`
  text-align: center;
  margin-bottom: 2rem;
`

const MainTitle = styled.h1`
  font-size: 2.5rem;
  font-weight: bold;
  color: #1f2937;
  margin-bottom: 1rem;

  @media (max-width: 768px) {
    font-size: 2rem;
  }
`

const MainSubtitle = styled.p`
  font-size: 1.25rem;
  color: #6b7280;
  max-width: 48rem;
  margin: 0 auto;
  line-height: 1.6;

  @media (max-width: 768px) {
    font-size: 1.125rem;
  }
`

const VB6Converter = () => {
  const [file, setFile] = useState(null)
  const [githubUrl, setGithubUrl] = useState("")
  const [isConverting, setIsConverting] = useState(false)
  const [conversionResult, setConversionResult] = useState(null)
  const [error, setError] = useState("")
  const [steps, setSteps] = useState([
    { id: "ingestor", name: "Ingestion", status: "pending", progress: 0 },
    { id: "parser", name: "Code Parsing", status: "pending", progress: 0 },
    { id: "context_analyzer", name: "Context Analysis", status: "pending", progress: 0 },
    { id: "summarizer", name: "Summarization", status: "pending", progress: 0 },
    { id: "generator", name: "Code Generation", status: "pending", progress: 0 },
    { id: "filebuilder", name: "Project Building", status: "pending", progress: 0 },
  ])
  const [overallProgress, setOverallProgress] = useState(0)
  const [conversionId, setConversionId] = useState(null)
  const pollingInterval = useRef(null)

  const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

  const resetSteps = () => {
    setSteps([
      { id: "ingestor", name: "Ingestion", status: "pending", progress: 0 },
      { id: "parser", name: "Code Parsing", status: "pending", progress: 0 },
      { id: "context_analyzer", name: "Context Analysis", status: "pending", progress: 0 },
      { id: "summarizer", name: "Summarization", status: "pending", progress: 0 },
      { id: "generator", name: "Code Generation", status: "pending", progress: 0 },
      { id: "filebuilder", name: "Project Building", status: "pending", progress: 0 },
    ])
    setOverallProgress(0)
    setConversionId(null)
  }

  const startStatusPolling = (conversionId) => {
    console.log("🚀 Starting status polling for:", conversionId)
    
    pollingInterval.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/conversion/status/${conversionId}`)
        
        if (response.ok) {
          const statusData = await response.json()
          console.log("📊 Status update:", statusData)
          
          // Update overall progress
          setOverallProgress(statusData.overall_progress)
          
          // Update individual steps
          setSteps(prevSteps => 
            prevSteps.map(step => {
              const backendStep = statusData.steps[step.id]
              if (backendStep) {
                return {
                  ...step,
                  status: backendStep.status,
                  progress: backendStep.progress
                }
              }
              return step
            })
          )
        }
      } catch (err) {
        console.error("🚨 Polling error:", err)
      }
    }, 1000) // Poll every 1 second
  }

  const stopStatusPolling = () => {
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current)
      pollingInterval.current = null
    }
  }

  useEffect(() => {
    return () => {
      stopStatusPolling()
    }
  }, [])

  const handleConvert = async () => {
    if (!file && !githubUrl) {
      setError("Please select a file or enter a GitHub URL")
      return
    }

    setIsConverting(true)
    setConversionResult(null)
    setError("")
    resetSteps()

    // Generate conversion ID for status tracking
    const newConversionId = Date.now().toString()
    setConversionId(newConversionId)

    // Initialize status tracking
    try {
      await fetch(`${API_BASE}/conversion/status/${newConversionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'initialize' })
      }).catch(() => {}) // Ignore errors if endpoint doesn't exist yet
    } catch (e) {}

    // Start status polling
    startStatusPolling(newConversionId)

    try {
      const formData = new FormData()
      if (file) {
        formData.append("zip_file", file)
      }
      if (githubUrl) {
        formData.append("github_link", githubUrl)
      }
      
      // Add conversion ID for tracking
      formData.append("conversion_id", newConversionId)

      // Your original convert call - this should return the file blob as before
      const response = await fetch(`${API_BASE}/convert`, {
        method: "POST",
        body: formData,
      })

      if (response.ok) {
        // Handle the file blob response as you originally did
        const blob = await response.blob()
        const downloadUrl = window.URL.createObjectURL(blob)
        
        setConversionResult({
          success: true,
          downloadUrl,
          duration: parseFloat(response.headers.get('X-Conversion-Time')) || 0
        })
        
        // Complete all steps
        setSteps(prevSteps =>
          prevSteps.map(step => ({
            ...step,
            status: "completed",
            progress: 100,
          }))
        )
        setOverallProgress(100)
      } else {
        const result = await response.json()
        setError(result.detail || "Conversion failed")
      }
    } catch (err) {
      setError("Network error: " + err.message)
    } finally {
      setIsConverting(false)
      stopStatusPolling()
    }
  }

  const handleDownload = () => {
    if (conversionResult?.downloadUrl) {
      const a = document.createElement("a")
      a.style.display = "none"
      a.href = conversionResult.downloadUrl
      a.download = "MyWindowsService.zip"
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(conversionResult.downloadUrl)
      document.body.removeChild(a)
    }
  }

  return (
    <MainContent>
      <HeaderSection>
        <MainTitle>Convert VB6 Projects to .NET 9 Worker Services</MainTitle>
        <MainSubtitle>
          Upload your VB6 project files or provide a GitHub repository link to automatically convert them into modern
          .NET 9 Worker Services with comprehensive logging and monitoring.
        </MainSubtitle>
      </HeaderSection>

      <UploadSection
        file={file}
        setFile={setFile}
        githubUrl={githubUrl}
        setGithubUrl={setGithubUrl}
        isConverting={isConverting}
        error={error}
        setError={setError}
        onConvert={handleConvert}
      />

      {(isConverting || conversionResult || error) && (
        <ConversionFlow
          steps={steps}
          overallProgress={overallProgress}
          conversionResult={conversionResult}
          onDownload={handleDownload}
          error={error}
        />
      )}
    </MainContent>
  )
}

export default VB6Converter
