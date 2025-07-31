"use client"

import styled from "styled-components"
import { Upload, FileText, Settings, Code, Package, CheckCircle, XCircle, Loader2, Download } from "lucide-react"
import Card from "./Card.jsx"
import Progress from "./Progress.jsx"
import Button from "./Button.jsx"
import Alert from "./alert.jsx"

const FlowTitle = styled.h2`
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.5rem;
`

const FlowDescription = styled.p`
  color: #6b7280;
  margin-bottom: 1.5rem;
`

const ProgressSection = styled.div`
  margin-bottom: 2rem;
`

const ProgressHeader = styled.div`
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
  color: #374151;
`

const StepsContainer = styled.div`
  position: relative;
  margin-bottom: 2rem;
`

const StepsFlow = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;

  @media (max-width: 768px) {
    flex-direction: column;
    align-items: stretch;
  }
`

const StepItem = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;
  max-width: 8rem;

  @media (max-width: 768px) {
    flex-direction: row;
    max-width: none;
    align-items: center;
    gap: 1rem;
  }
`

const StepConnector = styled.div`
  position: absolute;
  top: 1.5rem;
  left: 50%;
  width: 100%;
  height: 0.25rem;
  z-index: 1;

  @media (max-width: 768px) {
    display: none;
  }
`

const ConnectorLine = styled.div`
  height: 100%;
  background-color: #d1d5db;
  transition: all 0.5s ease;

  &.completed {
    background-color: #10b981;
  }

  &.running {
    background: linear-gradient(to right, #10b981 50%, #d1d5db 50%);
  }
`

const StepCircle = styled.div`
  width: 3rem;
  height: 3rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid;
  transition: all 0.3s ease;
  z-index: 2;
  position: relative;
  background: white;

  &.pending {
    border-color: #d1d5db;
    color: #9ca3af;
  }

  &.running {
    border-color: #2563eb;
    background-color: #2563eb;
    color: white;
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }

  &.completed {
    border-color: #10b981;
    background-color: #10b981;
    color: white;
  }

  &.failed {
    border-color: #ef4444;
    background-color: #ef4444;
    color: white;
  }
`

const StepIcon = styled.div`
  width: 1.5rem;
  height: 1.5rem;

  &.spinning {
    animation: spin 1s linear infinite;
  }
`

const StepInfo = styled.div`
  margin-top: 0.75rem;
  text-align: center;
  max-width: 8rem;

  @media (max-width: 768px) {
    text-align: left;
    margin-top: 0;
    max-width: none;
    flex: 1;
  }
`

const StepName = styled.p`
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: 0.25rem;

  &.pending {
    color: #6b7280;
  }

  &.running {
    color: #2563eb;
  }

  &.completed {
    color: #059669;
  }

  &.failed {
    color: #dc2626;
  }
`

const StepDescription = styled.p`
  font-size: 0.75rem;
  color: #6b7280;
  line-height: 1.3;
  margin-bottom: 0.5rem;
`

const StepProgress = styled.div`
  margin-top: 0.5rem;
`

const STEP_ICONS = {
  ingestor: Upload,
  parser: FileText,
  context_analyzer: Settings,
  summarizer: Code,
  generator: Code,
  filebuilder: Package,
}

const STEP_DESCRIPTIONS = {
  ingestor: "Ingesting VB6 project files from ZIP or GitHub",
  parser: "Parsing VB6 code to extract procedures and events",
  context_analyzer: "Analyzing application context and workflow",
  summarizer: "Summarizing parsed data for code generation",
  generator: "Generating .NET 9 Worker Service code",
  filebuilder: "Building and packaging the .NET project",
}

const ConversionFlow = ({ steps, overallProgress, conversionResult, onDownload, error }) => {
  const getStepIcon = (step) => {
    const Icon = STEP_ICONS[step.id]

    switch (step.status) {
      case "running":
        return (
          <StepIcon className="spinning">
            <Loader2 />
          </StepIcon>
        )
      case "completed":
        return (
          <StepIcon>
            <CheckCircle />
          </StepIcon>
        )
      case "failed":
        return (
          <StepIcon>
            <XCircle />
          </StepIcon>
        )
      default:
        return (
          <StepIcon>
            <Icon />
          </StepIcon>
        )
    }
  }

  const getConnectorStatus = (currentStep, index) => {
    if (currentStep.status === "completed") {
      return "completed"
    } else if (currentStep.status === "running") {
      return "running"
    }
    return ""
  }

  return (
    <Card>
      <FlowTitle>Conversion Progress</FlowTitle>
      <FlowDescription>Track the progress of your VB6 to .NET conversion through each step</FlowDescription>

      <ProgressSection>
        <ProgressHeader>
          <span>Overall Progress</span>
          <span>{overallProgress}%</span>
        </ProgressHeader>
        <Progress value={overallProgress} />
      </ProgressSection>

      <StepsContainer>
        <StepsFlow>
          {steps.map((step, index) => (
            <StepItem key={step.id}>
              {index < steps.length - 1 && (
                <StepConnector>
                  <ConnectorLine
                    className={getConnectorStatus(step, index)}
                  />
                </StepConnector>
              )}

              <StepCircle className={step.status}>{getStepIcon(step)}</StepCircle>

              <StepInfo>
                <StepName className={step.status}>{step.name}</StepName>
                <StepDescription>{STEP_DESCRIPTIONS[step.id]}</StepDescription>
                {step.status === "running" && (
                  <StepProgress>
                    <Progress value={step.progress} />
                  </StepProgress>
                )}
              </StepInfo>
            </StepItem>
          ))}
        </StepsFlow>
      </StepsContainer>

      {conversionResult && (
        <Alert variant="success">
          <CheckCircle style={{ width: "1rem", height: "1rem", marginRight: "0.5rem", marginTop: "0.125rem", flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <p style={{ fontWeight: 500, marginBottom: "0.25rem" }}>Conversion completed successfully!</p>
            <p style={{ fontSize: "0.875rem", opacity: 0.8 }}>
              Completed in {conversionResult.duration?.toFixed(2)} seconds
            </p>
          </div>
          <Button onClick={onDownload} variant="outline" size="sm" style={{ marginLeft: "auto" }}>
            <Download style={{ width: "1rem", height: "1rem", marginRight: "0.5rem" }} />
            Download Project
          </Button>
        </Alert>
      )}

      {error && !conversionResult && (
        <Alert variant="destructive">
          <XCircle style={{ width: "1rem", height: "1rem", marginRight: "0.5rem", marginTop: "0.125rem", flexShrink: 0 }} />
          <div>
            <p style={{ fontWeight: 500, marginBottom: "0.25rem" }}>Conversion failed</p>
            <p style={{ fontSize: "0.875rem", opacity: 0.8 }}>{error}</p>
          </div>
        </Alert>
      )}
    </Card>
  )
}

export default ConversionFlow
