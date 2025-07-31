import styled from "styled-components"
import Card from "./Card.jsx"

const LogTitle = styled.h2`
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.5rem;
`

const LogDescription = styled.p`
  color: #6b7280;
  margin-bottom: 1rem;
`

const LogContainer = styled.div`
  background-color: #1f2937;
  color: #10b981;
  padding: 1rem;
  border-radius: 0.5rem;
  font-family: "Courier New", monospace;
  font-size: 0.875rem;
  max-height: 24rem;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: #374151;
  }

  &::-webkit-scrollbar-thumb {
    background: #6b7280;
    border-radius: 3px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #9ca3af;
  }
`

const LogEntry = styled.div`
  margin-bottom: 0.25rem;
  word-wrap: break-word;
`

const LogTimestamp = styled.span`
  color: #6b7280;
`

const LogLevel = styled.span`
  margin-left: 0.5rem;

  &.error {
    color: #f87171;
  }

  &.warning {
    color: #fbbf24;
  }

  &.info {
    color: #60a5fa;
  }

  &.default {
    color: #10b981;
  }
`

const LogStage = styled.span`
  color: #a78bfa;
  margin-left: 0.5rem;
`

const LogMessage = styled.span`
  margin-left: 0.5rem;
`

const LogEmpty = styled.div`
  color: #6b7280;
  text-align: center;
  padding: 1rem;
  font-style: italic;
`

const LogStats = styled.div`
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  font-size: 0.875rem;
`

const LogStat = styled.div`
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  background-color: #374151;
  color: #d1d5db;
  
  &.error {
    background-color: #7f1d1d;
    color: #fca5a5;
  }
  
  &.warning {
    background-color: #78350f;
    color: #fcd34d;
  }
  
  &.info {
    background-color: #1e3a8a;
    color: #93c5fd;
  }
`

const LogViewer = ({ logs }) => {
  const getLevelClass = (level) => {
    switch (level) {
      case "ERROR":
        return "error"
      case "WARNING":
        return "warning"
      case "INFO":
        return "info"
      default:
        return "default"
    }
  }

  // Calculate log statistics
  const logStats = logs.reduce((acc, log) => {
    acc[log.level.toLowerCase()] = (acc[log.level.toLowerCase()] || 0) + 1
    return acc
  }, {})

  return (
    <Card>
      <LogTitle>Conversion Logs</LogTitle>
      <LogDescription>Real-time logs from the conversion process</LogDescription>

      {logs.length > 0 && (
        <LogStats>
          {Object.entries(logStats).map(([level, count]) => (
            <LogStat key={level} className={level}>
              {level.toUpperCase()}: {count}
            </LogStat>
          ))}
          <LogStat>TOTAL: {logs.length}</LogStat>
        </LogStats>
      )}

      <LogContainer>
        {logs.slice(-100).map((log) => (
          <LogEntry key={log.id}>
            <LogTimestamp>[{log.timestamp}]</LogTimestamp>
            <LogLevel className={getLevelClass(log.level)}>[{log.level}]</LogLevel>
            {log.stage && <LogStage>[{log.stage}]</LogStage>}
            {log.agent && <LogStage>[{log.agent}]</LogStage>}
            <LogMessage>{log.message}</LogMessage>
          </LogEntry>
        ))}
        {logs.length === 0 && <LogEmpty>No logs yet. Start a conversion to see real-time progress.</LogEmpty>}
      </LogContainer>
    </Card>
  )
}

export default LogViewer
