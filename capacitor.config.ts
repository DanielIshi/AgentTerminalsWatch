import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.spocky.agentterminals",
  appName: "AgentTerminalsWatch",
  webDir: "dist",
  server: {
    // For development: point to the local API server.
    // Remove or override for production APK.
    androidScheme: "https",
  },
};

export default config;
