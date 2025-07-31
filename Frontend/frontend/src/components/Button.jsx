"use client"

import styled from "styled-components"

const StyledButton = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  border-radius: 0.375rem;
  transition: all 0.2s;
  cursor: pointer;
  border: none;
  text-decoration: none;

  &:focus {
    outline: 2px solid #3b82f6;
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Variants */
  ${(props) =>
    props.variant === "primary" &&
    `
    background-color: #2563eb;
    color: white;
    
    &:hover:not(:disabled) {
      background-color: #1d4ed8;
    }
  `}

  ${(props) =>
    props.variant === "outline" &&
    `
    border: 1px solid #d1d5db;
    background-color: white;
    color: #374151;
    
    &:hover:not(:disabled) {
      background-color: #f9fafb;
    }
  `}

  ${(props) =>
    props.variant === "secondary" &&
    `
    background-color: #f3f4f6;
    color: #1f2937;
    
    &:hover:not(:disabled) {
      background-color: #e5e7eb;
    }
  `}

  /* Sizes */
  ${(props) =>
    props.size === "sm" &&
    `
    padding: 0.375rem 0.75rem;
    font-size: 0.875rem;
  `}

  ${(props) =>
    props.size === "md" &&
    `
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
  `}

  ${(props) =>
    props.size === "lg" &&
    `
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
  `}
`

const Button = ({ children, onClick, disabled = false, variant = "primary", size = "md", ...props }) => {
  return (
    <StyledButton onClick={onClick} disabled={disabled} variant={variant} size={size} {...props}>
      {children}
    </StyledButton>
  )
}

export default Button
