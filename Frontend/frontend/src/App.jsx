import { Box, Typography } from '@mui/material';
import { FileCode, Zap } from 'lucide-react';
import { Navbar } from './components/layout/Navbar';
import { Footer } from './components/layout/Footer';
import { ConverterForm } from './components/converter/ConverterForm';
import { ProgressCard } from './components/converter/ProgressCard';
import { HealthStatus } from './components/converter/HealthStatus';
import { AgentInfo } from './components/converter/AgentInfo';

export default function App() {
  return (
    <>
      <Navbar />
      <Box sx={{ py: 4, maxWidth: 1200, mx: 'auto', width: '100%' }}>
        <Box sx={{ textAlign: 'center', mb: 6 }}>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 2, mb: 2 }}>
            <FileCode className="h-8 w-8 text-primary" />
            <Typography variant="h1" sx={{ fontSize: { xs: '1.5rem', md: '2rem' } }}>
              VB6 to .NET Converter
            </Typography>
            <Zap className="h-8 w-8 text-secondary" />
          </Box>
          <Typography variant="body1" sx={{ maxWidth: '600px', mx: 'auto', color: 'text.secondary' }}>
            Transform your legacy VB6 projects into modern .NET 9 Worker Services using our advanced agentic AI framework.
          </Typography>
        </Box>

        <HealthStatus />
        <Box sx={{ display: 'grid', gap: 4, gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, mb: 4 }}>
          <ConverterForm />
          <ProgressCard />
        </Box>
        <AgentInfo />
      </Box>
      <Footer />
    </>
  );
}
