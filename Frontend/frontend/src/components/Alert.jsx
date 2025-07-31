import styled from "styled-components"

const AlertContainer = styled.div`
  display: flex;
  align-items: flex-start;
  padding: 1rem;
  border: 1px solid;
  border-radius: 0.375rem;
  margin-bottom: 1rem;

  ${(props) =>
    props.variant === "default" &&
    `
    background-color: #dbeafe;
    border-color: #bfdbfe;
    color: #1e40af;
  `}

  ${(props) =>
    props.variant === "success" &&
    `
    background-color: #dcfce7;
    border-color: #bbf7d0;
    color: #166534;
  `}

  ${(props) =>
    props.variant === "destructive" &&
    `
    background-color: #fef2f2;
    border-color: #fecaca;
    color: #dc2626;
  `}
`

const Alert = ({ children, variant = "default", ...props }) => {
  return (
    <AlertContainer variant={variant} {...props}>
      {children}
    </AlertContainer>
  )
}

export default Alert
