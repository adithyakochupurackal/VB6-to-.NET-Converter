import styled from "styled-components"

const ProgressContainer = styled.div`
  width: 100%;
  background-color: #e5e7eb;
  border-radius: 9999px;
  height: 0.5rem;
  overflow: hidden;
`

const ProgressBar = styled.div`
  background-color: #2563eb;
  height: 100%;
  transition: width 0.3s ease-out;
  border-radius: 9999px;
  width: ${(props) => Math.min(100, Math.max(0, props.$value || 0))}%;
`

const Progress = ({ value = 0, ...props }) => {
  return (
    <ProgressContainer {...props}>
      <ProgressBar $value={value} />
    </ProgressContainer>
  )
}

export default Progress
