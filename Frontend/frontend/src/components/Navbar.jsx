import styled from "styled-components"
import { Code } from "lucide-react"
import Badge from "./Badge.jsx"

const NavContainer = styled.nav`
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border-bottom: 1px solid #e2e8f0;
`

const NavWrapper = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1rem;
`

const NavContent = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 4rem;
`

const NavBrand = styled.div`
  display: flex;
  align-items: center;
`

const NavIcon = styled(Code)`
  width: 2rem;
  height: 2rem;
  color: #2563eb;
`

const NavTitle = styled.span`
  margin-left: 0.5rem;
  font-size: 1.25rem;
  font-weight: bold;
  color: #1f2937;
`

const NavInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;

  @media (max-width: 768px) {
    flex-direction: column;
    gap: 0.5rem;
  }
`

const NavSubtitle = styled.div`
  font-size: 0.875rem;
  color: #6b7280;

  @media (max-width: 768px) {
    display: none;
  }
`

const Navbar = () => {
  return (
    <NavContainer>
      <NavWrapper>
        <NavContent>
          <NavBrand>
            <NavIcon />
            <NavTitle>VB6 to .NET Converter</NavTitle>
          </NavBrand>
          <NavInfo>
            <Badge variant="secondary">v2.0.6</Badge>
            <NavSubtitle>Powered by Azure OpenAI</NavSubtitle>
          </NavInfo>
        </NavContent>
      </NavWrapper>
    </NavContainer>
  )
}

export default Navbar
