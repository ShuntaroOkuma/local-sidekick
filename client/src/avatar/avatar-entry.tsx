import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AvatarApp } from "./AvatarApp";

const root = document.getElementById("avatar-root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <AvatarApp />
    </StrictMode>,
  );
}
