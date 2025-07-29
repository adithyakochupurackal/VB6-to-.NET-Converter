import React, { useState } from "react";
import { Box, Typography, Menu, MenuItem } from "@mui/material";
import AccountCircle from "@mui/icons-material/AccountCircle";
import styled from "@emotion/styled";

// styled wrapper (you can keep this name or rename as you like)
const NavBarContainer = styled(Box)`
  background: linear-gradient(90deg, #1a202c 0%, #2d3748 100%);
  padding: 1.5rem 2rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  position: sticky;
  top: 0;
  z-index: 1000;
  border-radius: 16px;
`;

// 👉 Named export
export function Navbar() {
  const [anchorEl, setAnchorEl] = useState(null);

  const handleMenuOpen = (e) => setAnchorEl(e.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);
  const handleLogout = () => {
    handleMenuClose();
    console.log("User logged out");
  };

  return (
    <NavBarContainer>
      <Box
        display="flex"
        alignItems="center"
        gap={2}
        maxWidth="1280px"
        mx="auto"
        width="100%"
      >
        <img src="/ustlogo.svg" alt="UST Logo" style={{ height: 48 }} />
        <Typography variant="h5" sx={{ color: "#fff", fontWeight: 700 }}>
          VB6 to .NET Converter
        </Typography>

        <Box ml="auto">
          <AccountCircle
            sx={{ color: "#fff", fontSize: 32, cursor: "pointer" }}
            onClick={handleMenuOpen}
          />
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
          >
            <MenuItem onClick={handleLogout}>Logout</MenuItem>
          </Menu>
        </Box>
      </Box>
    </NavBarContainer>
  );
}
