import styled from "styled-components"
import Badge from "./Badge.jsx"

const FooterContainer = styled.footer`
  background: white;
  border-top: 1px solid #e2e8f0;
  margin-top: 4rem;
`

const FooterWrapper = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem 1rem;
`

const FooterContent = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 2rem;
  margin-bottom: 2rem;
`

const FooterSection = styled.div`
  display: flex;
  flex-direction: column;
`

const FooterTitle = styled.h3`
  font-size: 1.125rem;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 1rem;
`

const FooterText = styled.p`
  color: #6b7280;
  line-height: 1.6;
`

const FooterList = styled.ul`
  list-style: none;
  color: #6b7280;

  li {
    margin-bottom: 0.5rem;
  }
`

const FooterBottom = styled.div`
  padding-top: 2rem;
  border-top: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;

  @media (max-width: 768px) {
    flex-direction: column;
    gap: 1rem;
    text-align: center;
  }
`

const FooterCopyright = styled.p`
  color: #6b7280;
`

const FooterBadges = styled.div`
  display: flex;
  gap: 1rem;
`

const Footer = () => {
  return (
    <FooterContainer>
      <FooterWrapper>
        <FooterContent>
          <FooterSection>
            <FooterTitle>VB6 to .NET Converter</FooterTitle>
            <FooterText>
              Automatically convert your legacy VB6 applications to modern .NET 9 Worker Services with comprehensive
              error handling and logging.
            </FooterText>
          </FooterSection>
          <FooterSection>
            <FooterTitle>Features</FooterTitle>
            <FooterList>
              <li>• Automated VB6 code parsing</li>
              <li>• Context-aware conversion</li>
              <li>• .NET 9 Worker Service generation</li>
              <li>• Real-time progress tracking</li>
              <li>• Comprehensive logging</li>
            </FooterList>
          </FooterSection>
          <FooterSection>
            <FooterTitle>Supported Files</FooterTitle>
            <FooterList>
              <li>• .frm (VB6 Forms)</li>
              <li>• .bas (VB6 Modules)</li>
              <li>• .cls (VB6 Classes)</li>
              <li>• .vbp (VB6 Projects)</li>
              <li>• GitHub Repositories</li>
            </FooterList>
          </FooterSection>
        </FooterContent>
        <FooterBottom>
          <FooterCopyright>© 2024 VB6 to .NET Converter. Built with FastAPI and React.</FooterCopyright>
          <FooterBadges>
            <Badge variant="outline">FastAPI Backend</Badge>
            <Badge variant="outline">React Frontend</Badge>
          </FooterBadges>
        </FooterBottom>
      </FooterWrapper>
    </FooterContainer>
  )
}

export default Footer
