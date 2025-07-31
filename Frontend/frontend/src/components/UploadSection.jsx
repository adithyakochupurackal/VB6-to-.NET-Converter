"use client"

import { useRef } from "react"
import styled from "styled-components"
import { Upload, Github, Code, Loader2 } from "lucide-react"
import Card from "./Card.jsx"
import Button from "./Button.jsx"
import Alert from "./alert.jsx"

const UploadHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
`

const UploadIcon = styled(Upload)`
  width: 1.25rem;
  height: 1.25rem;
  color: #2563eb;
`

const UploadTitle = styled.h2`
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
`

const UploadDescription = styled.p`
  color: #6b7280;
  margin-bottom: 1.5rem;
`

const UploadGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-bottom: 1.5rem;
`

const UploadField = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
`

const UploadLabel = styled.label`
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  display: flex;
  align-items: center;
  gap: 0.5rem;
`

const GithubIcon = styled(Github)`
  width: 1rem;
  height: 1rem;
`

const FileInput = styled.input`
  display: block;
  width: 100%;
  font-size: 0.875rem;
  color: #6b7280;
  cursor: pointer;
  background-color: white;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  padding: 0.5rem;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

const GithubInput = styled.input`
  display: block;
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 0.875rem;

  &:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

const FileInfo = styled.p`
  font-size: 0.875rem;
  color: #059669;
`

const UploadActions = styled.div`
  display: flex;
  justify-content: center;
`

const ButtonContent = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
`

const ButtonIcon = styled.div`
  width: 1rem;
  height: 1rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  svg {
    width: 100%;
    height: 100%;
  }

  &.spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
`

const UploadSection = ({ file, setFile, githubUrl, setGithubUrl, isConverting, error, setError, onConvert }) => {
  const fileInputRef = useRef(null)

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

  return (
    <Card>
      <UploadHeader>
        <UploadIcon />
        <UploadTitle>Upload VB6 Project</UploadTitle>
      </UploadHeader>
      <UploadDescription>
        Choose a ZIP file containing your VB6 project or provide a GitHub repository URL
      </UploadDescription>

      <UploadGrid>
        <UploadField>
          <UploadLabel htmlFor="file-upload">Upload ZIP File</UploadLabel>
          <FileInput
            id="file-upload"
            type="file"
            accept=".zip"
            onChange={handleFileChange}
            ref={fileInputRef}
            disabled={isConverting}
          />
          {file && (
            <FileInfo>
              Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
            </FileInfo>
          )}
        </UploadField>

        <UploadField>
          <UploadLabel htmlFor="github-url">
            <GithubIcon />
            GitHub Repository URL
          </UploadLabel>
          <GithubInput
            id="github-url"
            type="url"
            placeholder="https://github.com/username/repository"
            value={githubUrl}
            onChange={handleGithubUrlChange}
            disabled={isConverting}
          />
        </UploadField>
      </UploadGrid>

      {error && (
        <Alert variant="destructive">
          <XCircle style={{ width: "1rem", height: "1rem", marginRight: "0.5rem", marginTop: "0.125rem", flexShrink: 0 }} />
          <div>{error}</div>
        </Alert>
      )}

      <UploadActions>
        <Button onClick={onConvert} disabled={isConverting || (!file && !githubUrl)} size="lg">
          <ButtonContent>
            {isConverting ? (
              <>
                <ButtonIcon className="spinning">
                  <Loader2 />
                </ButtonIcon>
                Converting...
              </>
            ) : (
              <>
                <ButtonIcon>
                  <Code />
                </ButtonIcon>
                Start Conversion
              </>
            )}
          </ButtonContent>
        </Button>
      </UploadActions>
    </Card>
  )
}

export default UploadSection
