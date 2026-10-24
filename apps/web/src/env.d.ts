/// <reference types="vite/client" />

declare global {
  interface Window {
    ryanDam: {
      getBackendInfo(): Promise<{ baseUrl: string; token: string; version: string }>;
      selectFiles(): Promise<string[]>;
      createSampleFile(): Promise<{ name: string }>;
      startSampleDrag(): void;
    };
  }
}

export {};
