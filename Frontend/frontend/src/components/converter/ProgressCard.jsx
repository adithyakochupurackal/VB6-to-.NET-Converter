import { useConverter } from "../../hooks/useConverter";
import { Box, Card, Typography, LinearProgress } from "@mui/material";

export function ProgressCard() {
  const {
    progress,
    currentAgent,
    stageDescription,
    logs,
    isConverting,
    error,
  } = useConverter();

  console.log("ProgressCard rendering with logs:", logs); // Debug logs

  return (
    <Card sx={{ maxWidth: 600, mx: "auto", p: 2, mt: 2 }}>
      <Typography variant="h6">Conversion Progress</Typography>
      {error && (
        <Typography variant="body2" sx={{ color: "error.main", mb: 2 }}>
          Error: {error}
        </Typography>
      )}
      <Typography variant="body2">Agent: {currentAgent || "N/A"}</Typography>
      <Typography variant="body2">
        Stage: {stageDescription || "N/A"}
      </Typography>
      <LinearProgress variant="determinate" value={progress} sx={{ my: 2 }} />
      <Typography variant="body2">Progress: {progress}%</Typography>
      <Box sx={{ mt: 2, maxHeight: 200, overflowY: "auto" }}>
        <Typography variant="h6">Logs</Typography>
        {logs.length === 0 && (
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            No logs available
          </Typography>
        )}
        {logs.map((log, index) => (
          <Typography
            key={index}
            variant="body2"
            sx={{
              color: log.level === "ERROR" ? "error.main" : "text.primary",
            }}
          >
            [{log.event_type}] {log.message} (Stage: {log.stage}, Agent:{" "}
            {log.agent || "N/A"})
          </Typography>
        ))}
      </Box>
    </Card>
  );
}
