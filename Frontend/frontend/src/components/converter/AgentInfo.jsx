import { Box, Card, Typography } from '@mui/material';

export function AgentInfo() {
  const agents = [
    { name: 'IngestorAgent', desc: 'Extracts VB6 files' },
    { name: 'ParserAgent', desc: 'Parses code structure' },
    { name: 'ContextAnalyzerAgent', desc: 'Analyzes application context' },
    { name: 'SummarizerAgent', desc: 'Summarizes parsed data' },
    { name: 'GeneratorAgent', desc: 'Generates C# code' },
    { name: 'FileBuilderAgent', desc: 'Creates .NET project' },
  ];

  return (
    <Card>
      <Box sx={{ p: 3 }}>
        <Typography variant="h4">Agentic AI Framework</Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
          Our autonomous AI agents work together to convert your VB6 project
        </Typography>
      </Box>
      <Box sx={{ px: 3, pb: 3 }}>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)', lg: 'repeat(6, 1fr)' } }}>
          {agents.map((agent, index) => (
            <Box key={index} sx={{ textAlign: 'center', p: 2, border: 1, borderColor: 'grey.300', borderRadius: 1 }}>
              <Box sx={{ width: 32, height: 32, bgcolor: 'primary.light', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 'auto', mb: 1 }}>
                <Typography sx={{ color: 'primary.main', fontWeight: 'bold' }}>{index + 1}</Typography>
              </Box>
              <Typography variant="body2" sx={{ fontWeight: 'medium' }}>{agent.name}</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>{agent.desc}</Typography>
            </Box>
          ))}
        </Box>
      </Box>
    </Card>
  );
}
