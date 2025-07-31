import styled from "styled-components"

const StyledBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;

  ${(props) =>
    props.variant === "default" &&
    `
    background-color: #dbeafe;
    color: #1e40af;
  `}

  ${(props) =>
    props.variant === "secondary" &&
    `
    background-color: #f3f4f6;
    color: #374151;
  `}

  ${(props) =>
    props.variant === "outline" &&
    `
    border: 1px solid #d1d5db;
    color: #374151;
    background-color: white;
  `}
`

const Badge = ({ children, variant = "default", ...props }) => {
  return (
    <StyledBadge variant={variant} {...props}>
      {children}
    </StyledBadge>
  )
}

export default Badge
