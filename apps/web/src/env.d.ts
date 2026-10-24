/// <reference types="vite/client" />

declare global {
  interface Window {
    ryanDam: {
      getBackendInfo(): Promise<{ baseUrl: string; token: string; version: string }>;
      selectFiles(): Promise<string[]>;
      selectFolder(): Promise<string | null>;
      createSampleFile(): Promise<{ name: string }>;
      startSampleDrag(): void;
    };
  }
}

export {};
