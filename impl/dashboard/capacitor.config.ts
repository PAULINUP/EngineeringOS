import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "br.com.paulinup.engineeringos",
  appName: "EngineeringOS",
  webDir: "dist",
  server: {
    androidScheme: "https",
    // O backend local roda em HTTP durante o desenvolvimento; sem isto o
    // Android bloqueia tráfego cleartext e o app não conecta em rede local.
    cleartext: true,
  },
  plugins: {
    // Roteia fetch/XHR pela camada nativa: elimina CORS e mixed-content para
    // a API (o WebView não é a origem do backend).
    CapacitorHttp: {
      enabled: true,
    },
    StatusBar: {
      style: "LIGHT",
      backgroundColor: "#060913",
      overlaysWebView: false,
    },
    SplashScreen: {
      launchShowDuration: 1200,
      backgroundColor: "#060913",
      showSpinner: false,
      androidScaleType: "CENTER_CROP",
    },
  },
  android: {
    allowMixedContent: true,
  },
};

export default config;
