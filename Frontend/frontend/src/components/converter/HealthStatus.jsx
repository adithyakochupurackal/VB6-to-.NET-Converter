import { Box, Card, Typography, Chip, Button } from "@mui/material";
import { Activity, RefreshCw } from "lucide-react";
import { useConverter } from "../../hooks/useConverter";

export function HealthStatus() {
  const { healthStatus, checkHealth } = useConverter();

  const handleCheckHealth = () => {
    checkHealth();
  };

  return (
    <Card sx={{ maxWidth: 400, mx: "auto", mb: 4 }}>
      <Box sx={{ p: 2, display: "flex", flexDirection: "column", gap: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Activity className="h-5 w-5" />
          <Typography variant="body2">API Status:</Typography>
          {healthStatus ? (
            <>
              <Chip
                label={healthStatus.status}
                color={healthStatus.status === "healthy" ? "success" : "error"}
                size="small"
              />
              {healthStatus.azure_openai && (
                <Chip
                  label={`Azure OpenAI: ${healthStatus.azure_openai}`}
                  variant="outlined"
                  size="small"
                />
              )}
            </>
          ) : (
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              Click to check API status
            </Typography>
          )}
        </Box>
        {healthStatus?.error && (
          <Typography variant="body2" sx={{ color: "error.main" }}>
            {healthStatus.error}
          </Typography>
        )}
        <Button
          variant="outlined"
          size="small"
          startIcon={<RefreshCw className="h-4 w-4" />}
          onClick={handleCheckHealth}
          sx={{ alignSelf: "flex-start" }}
        >
          Check API Status
        </Button>
      </Box>
    </Card>
  );
}
