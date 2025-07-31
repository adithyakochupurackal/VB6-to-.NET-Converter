"use client"

import { useState, useEffect, useRef } from "react"
import {
  Upload,
  Download,
  Github,
  FileText,
  Settings,
  Code,
  Package,
  CheckCircle,
  AlertCircle,
  Loader2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"

const CONVERSION_STEPS = [
  {
    id: "ingestor",
    name: "Ingestion",
    description: "Ingesting VB6 project files",
    icon: Upload,
    color: "bg-blue-500",
  },
  {
    id: "parser",
    name: "Code Parsing",
    description: "Parses VB6 code structure",
    icon: FileText,
    color: "bg-green-500",
  },
  {
    id: "context_analyzer",
    name: "Context Analysis",
    description: "Analyzes application context and workflow",
    icon: Settings,
    color: "bg-purple-500",
  },
  {
    id: "summarizer",
    name: "Summarization",
    description: "Summarizes parsed data for code generation",
    icon: Code,
    color: "bg-orange-500",
  },
  {
    id: "generator",
    name: "Code Generation",
    description: "Generates .NET 9 Worker Service code",
    icon: Code,
    color: "bg-red-500",
  },
  {
    id: "filebuilder",
    name: "Building Project",
    description: "Builds and packages the .NET project",
    icon: Package,
    color: "bg-indigo-500",
  },
]

export default function VB6Converter() {
  const [file, setFile] = useState(null)
  const [githubUrl, setGithubUrl] = useState("")
  const [isConverting, setIsConverting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState("")
  const [completedSteps, setCompletedSteps] = useState(new Set())
  const [conversionResult, setConversionResult] = useState(null)
  const [error, setError] = useState("")
  const [logs, setLogs] = useState([])
  const eventSourceRef = useRef(null)
  const fileInputRef = useRef(null)

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0]
    if (selectedFile) {
      if (selectedFile.size > 50 * 1024 * 1024) {
        setError("File size must be less than 50MB")
        return
      }
      setFile(selectedFile)
      setGithubUrl("")
      setError("")
    }
  }

  const handleGithubUrlChange = (event) => {
    setGithubUrl(event.target.value)
    if (event.target.value) {
      setFile(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
    }
    setError("")
  }

  const startSSEConnection = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    eventSourceRef.current = new EventSource(`${API_BASE}/stream`)

    eventSourceRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        setLogs((prev) => [
          ...prev,
          {
            id: Date.now() + Math.random(),
            timestamp: new Date(data.timestamp * 1000).toLocaleTimeString(),
            level: data.level,
            message: data.message,
            stage: data.stage,
            agent: data.agent,
          },
        ])

        if (data.progress !== undefined) {
          setProgress(data.progress)
        }

        if (data.current_agent) {
          setCurrentStep(data.current_agent.toLowerCase())
        }

        if (data.state === "Completed" && data.agent) {
          setCompletedSteps((prev) => new Set([...prev, data.agent.toLowerCase()]))
        }

        if (data.stage === "pipeline" && data.state === "Completed") {
          setIsConverting(false)
          setCurrentStep("")
        }

        if (data.stage === "pipeline" && data.state === "Failed") {
          setIsConverting(false)
          setCurrentStep("")
          setError(data.message || "Conversion failed")
        }
      } catch (err) {
        console.error("Error parsing SSE data:", err)
      }
    }

    eventSourceRef.current.onerror = (event) => {
      console.error("SSE connection error:", event)
    }
  }

  const handleConvert = async () => {
    if (!file && !githubUrl) {
      setError("Please select a file or enter a GitHub URL")
      return
    }

    setIsConverting(true)
    setProgress(0)
    setCurrentStep("")
    setCompletedSteps(new Set())
    setConversionResult(null)
    setError("")
    setLogs([])

    startSSEConnection()

    try {
      const formData = new FormData()
      if (file) {
        formData.append("zip_file", file)
      }
      if (githubUrl) {
        formData.append("github_link", githubUrl)
      }

      const response = await fetch(`${API_BASE}/convert`, {
        method: "POST",
        body: formData,
      })

      const result = await response.json()

      if (response.ok) {
        setConversionResult(result)
        setProgress(100)
      } else {
        setError(result.detail || "Conversion failed")
        setIsConverting(false)
      }
    } catch (err) {
      setError("Network error: " + err.message)
      setIsConverting(false)
    }
  }

  const handleDownload = async () => {
    if (!conversionResult?.conversion_id) return

    try {
      const response = await fetch(`${API_BASE}/download/${conversionResult.conversion_id}`)
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.style.display = "none"
        a.href = url
        a.download = "MyWindowsService.zip"
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      } else {
        setError("Download failed")
      }
    } catch (err) {
      setError("Download error: " + err.message)
    }
  }

  const getStepStatus = (stepId) => {
    if (completedSteps.has(stepId)) return "completed"
    if (currentStep === stepId) return "active"
    return "pending"
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Navigation */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <div className="flex-shrink-0 flex items-center">
                <Code className="h-8 w-8 text-blue-600" />
                <span className="ml-2 text-xl font-bold text-gray-900">VB6 to .NET Converter</span>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <Badge variant="secondary">v2.0.6</Badge>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Convert VB6 Projects to .NET 9 Worker Services</h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Upload your VB6 project files or provide a GitHub repository link to automatically convert them into modern
            .NET 9 Worker Services with comprehensive logging and monitoring.
          </p>
        </div>

        {/* Upload Section */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Upload VB6 Project
            </CardTitle>
            <CardDescription>
              Choose a ZIP file containing your VB6 project or provide a GitHub repository URL
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label htmlFor="file-upload">Upload ZIP File</Label>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".zip"
                  onChange={handleFileChange}
                  ref={fileInputRef}
                  disabled={isConverting}
                />
                {file && (
                  <p className="text-sm text-gray-600">
                    Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="github-url" className="flex items-center gap-2">
                  <Github className="h-4 w-4" />
                  GitHub Repository URL
                </Label>
                <Input
                  id="github-url"
                  type="url"
                  placeholder="https://github.com/username/repository"
                  value={githubUrl}
                  onChange={handleGithubUrlChange}
                  disabled={isConverting}
                />
              </div>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex justify-center">
              <Button
                onClick={handleConvert}
                disabled={isConverting || (!file && !githubUrl)}
                size="lg"
                className="px-8"
              >
                {isConverting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Converting...
                  </>
                ) : (
                  <>
                    <Code className="mr-2 h-4 w-4" />
                    Start Conversion
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Progress Section */}
        {(isConverting || conversionResult) && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Conversion Progress</CardTitle>
              <CardDescription>Track the progress of your VB6 to .NET conversion</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Overall Progress</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} className="w-full" />
              </div>

              {/* Horizontal Step Flow */}
              <div className="relative">
                <div className="flex items-center justify-between">
                  {CONVERSION_STEPS.map((step, index) => {
                    const status = getStepStatus(step.id)
                    const Icon = step.icon

                    return (
                      <div key={step.id} className="flex flex-col items-center relative">
                        {/* Connection Line */}
                        {index < CONVERSION_STEPS.length - 1 && (
                          <div
                            className="absolute top-6 left-full w-full h-0.5 bg-gray-200 -z-10"
                            style={{ width: "calc(100vw / 6 - 2rem)" }}
                          >
                            <div
                              className={`h-full transition-all duration-500 ${
                                completedSteps.has(step.id) ? "bg-green-500" : "bg-gray-200"
                              }`}
                              style={{
                                width: completedSteps.has(step.id) ? "100%" : "0%",
                              }}
                            />
                          </div>
                        )}

                        {/* Step Circle */}
                        <div
                          className={`
                          w-12 h-12 rounded-full flex items-center justify-center border-2 transition-all duration-300
                          ${
                            status === "completed"
                              ? "bg-green-500 border-green-500 text-white"
                              : status === "active"
                                ? `${step.color} border-current text-white animate-pulse`
                                : "bg-white border-gray-300 text-gray-400"
                          }
                        `}
                        >
                          {status === "completed" ? (
                            <CheckCircle className="h-6 w-6" />
                          ) : status === "active" ? (
                            <Loader2 className="h-6 w-6 animate-spin" />
                          ) : (
                            <Icon className="h-6 w-6" />
                          )}
                        </div>

                        {/* Step Info */}
                        <div className="mt-2 text-center max-w-24">
                          <p
                            className={`text-sm font-medium ${
                              status === "completed"
                                ? "text-green-600"
                                : status === "active"
                                  ? "text-blue-600"
                                  : "text-gray-500"
                            }`}
                          >
                            {step.name}
                          </p>
                          <p className="text-xs text-gray-500 mt-1 leading-tight">{step.description}</p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Success Message */}
              {conversionResult && (
                <Alert className="border-green-200 bg-green-50">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <AlertDescription className="text-green-800">
                    Conversion completed successfully in {conversionResult.duration?.toFixed(2)} seconds!
                    <Button onClick={handleDownload} variant="outline" size="sm" className="ml-4 bg-transparent">
                      <Download className="mr-2 h-4 w-4" />
                      Download Project
                    </Button>
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        )}

        {/* Logs Section */}
        {logs.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Conversion Logs</CardTitle>
              <CardDescription>Real-time logs from the conversion process</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm max-h-96 overflow-y-auto">
                {logs.map((log) => (
                  <div key={log.id} className="mb-1">
                    <span className="text-gray-500">[{log.timestamp}]</span>
                    <span
                      className={`ml-2 ${
                        log.level === "ERROR"
                          ? "text-red-400"
                          : log.level === "WARNING"
                            ? "text-yellow-400"
                            : log.level === "INFO"
                              ? "text-blue-400"
                              : "text-green-400"
                      }`}
                    >
                      [{log.level}]
                    </span>
                    {log.stage && <span className="text-purple-400 ml-2">[{log.stage}]</span>}
                    <span className="ml-2">{log.message}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-16">
        <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">VB6 to .NET Converter</h3>
              <p className="text-gray-600">
                Automatically convert your legacy VB6 applications to modern .NET 9 Worker Services with comprehensive
                error handling and logging.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Features</h3>
              <ul className="space-y-2 text-gray-600">
                <li>• Automated VB6 code parsing</li>
                <li>• Context-aware conversion</li>
                <li>• .NET 9 Worker Service generation</li>
                <li>• Real-time progress tracking</li>
                <li>• Comprehensive logging</li>
              </ul>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Supported Files</h3>
              <ul className="space-y-2 text-gray-600">
                <li>• .frm (VB6 Forms)</li>
                <li>• .bas (VB6 Modules)</li>
                <li>• .cls (VB6 Classes)</li>
                <li>• .vbp (VB6 Projects)</li>
                <li>• GitHub Repositories</li>
              </ul>
            </div>
          </div>
          <div className="mt-8 pt-8 border-t border-gray-200">
            <p className="text-center text-gray-500">© 2024 VB6 to .NET Converter. Built with FastAPI and React.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
