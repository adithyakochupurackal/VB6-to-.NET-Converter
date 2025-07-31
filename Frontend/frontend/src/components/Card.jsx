import styled from "styled-components"

const CardContainer = styled.div`
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  padding: 1.5rem;
  margin-bottom: 2rem;
`

const Card = ({ children, className = "" }) => {
  return <CardContainer className={className}>{children}</CardContainer>
}

export default Card
